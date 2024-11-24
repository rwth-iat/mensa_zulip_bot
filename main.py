#!/usr/bin/env python3

# Copyright 2020 by Michael Thies <mail@mhthies.de>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Zulip bot for sending Mensa Academica Aachen's menu to the PLT Zulip chat every workday at 11:25.
"""
import configparser
import datetime
import logging
from typing import Iterable

import time
import os.path

import pytz
import zulip
import mensa_aachen

__author__ = "Michael Thies <mail@mhthies.de>"
__version__ = "1.0"

INFO_TIME = datetime.time(11, 25, 00, tzinfo=pytz.timezone('Europe/Berlin'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main_loop():
    logger.info("Initializing client ...")
    config_file = os.path.join(os.path.dirname(__file__), "config.ini")
    config = configparser.ConfigParser()
    config.read(config_file)
    zulip_client = zulip.Client(config_file=config_file)
    stream_name = config['message']['stream']
    logger.info("Starting into main loop ...")
    while True:
        try:
            # Calculate time until message and sleep
            sleep_time = calculate_sleep_time()
            logger.info("Scheduling next message for {}.".format(sleep_time))
            logarithmic_sleep(sleep_time)

            # Send messages
            send_menu(zulip_client, stream_name)

            # Prevent fast retriggering
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt. Exiting …")
            return
        except Exception as e:
            logger.error("Exception in main loop:", exc_info=e)


def calculate_sleep_time() -> datetime.datetime:
    now = datetime.datetime.now(tz=INFO_TIME.tzinfo)
    res = now.replace(hour=INFO_TIME.hour, minute=INFO_TIME.minute, second=INFO_TIME.second,
                      microsecond=INFO_TIME.microsecond)
    if res <= now:
        res += datetime.timedelta(days=1)

    # Skip the weekend
    if res.weekday() >= 5:
        res += datetime.timedelta(days=7 - res.weekday())

    return res


def logarithmic_sleep(target: datetime.datetime):
    while True:
        diff = (target - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds()
        if diff < 0.2:
            time.sleep(diff)
            return
        else:
            time.sleep(diff/2)


def send_menu(client: zulip.Client, stream: str):
    logger.info("Fetching menu data ...")
    try:
        menu_data = mensa_aachen.get_dishes(mensa_aachen.Canteens.MENSA_ACADEMICA)
        menu = menu_data[datetime.date.today()]
    except Exception as e:
        logger.error("Error while fetching canteen menu:", exc_info=e)
        return
    logger.info("Fetching menu data finished.")

    filtered_dishes = [dish for dish in menu.main_dishes
                       if dish.menu_category not in ("Pizza Classics", "Burger Classics", "Fingerfood",
                                                     "Ofenkartoffel")]
    formatted_menu = (
        "# Speiseplan Mensa Academica {:%d.%m.%Y}\n\n"
        "| | Gericht | Fleisch |\n|---|---|---|\n".format(datetime.date.today())
        + "\n".join(
            "| **{}** | {}{} | {} |".format(
                dish.menu_category,
                dish.main_component.title,
                " 〈{}〉".format(" • ".join(c.title for c in dish.aux_components)) if dish.aux_components else "",
                meat_emojis(dish.meat))
            for dish in filtered_dishes)
        + "\n\n Dazu:\n\n* {}, sowie\n* {}".format(
            " oder ".join(dish.main_component.title
                          for dish in menu.side_dishes
                          if dish.menu_category == "Hauptbeilagen"),
            " oder ".join(dish.main_component.title for
                          dish in menu.side_dishes
                          if dish.menu_category == "Nebenbeilage"))
    )

    subject = "Mensa Speiseplan {:%d.%m.%Y}".format(datetime.date.today())
    logger.info("Sending messages ...")
    client.send_message({
        "type": "stream",
        "to": [stream],
        "subject": subject,
        "content": formatted_menu,
    })

    client.send_message({
        "type": "stream",
        "to": [stream],
        "subject": subject,
        "content": "@all Wer kommt mit essen? Bitte mit 👍 oder 👎 reagieren.",
    })
    logger.info("Sending messages finished.")


MEAT_ICONS = {
    mensa_aachen.MeatType.RIND: "🐂",
    mensa_aachen.MeatType.SCHWEIN: "🐖",
    mensa_aachen.MeatType.GEFLUEGEL: "🐔",
    mensa_aachen.MeatType.VEGETARIAN: "🧀",
    mensa_aachen.MeatType.VEGAN: "🥦",
    mensa_aachen.MeatType.FISCH: "🐟",
}


def meat_emojis(meat: Iterable[mensa_aachen.MeatType]) -> str:
    meat = set(meat)
    if mensa_aachen.MeatType.VEGAN in meat:
        meat.discard(mensa_aachen.MeatType.VEGETARIAN)
    return " ".join(MEAT_ICONS[m] for m in meat)


if __name__ == "__main__":
    main_loop()
