import argparse
import json
import math
import os
import re
import sys

import requests


def handle_special_ids(id):
    if id == "P3_Unique_Ring_107":
        return "Unique_Ring_107_x1"
    else:
        return id


def main(url, output):
    # get the build id from the url
    buildId = url.split('/')[-1].split('#')[0]

    #### Get data ####

    # make a http get request to the d3planner api
    r = requests.get('https://planners.maxroll.gg/profiles/d3/' + buildId)

    # check if the request was successful
    if r.status_code != 200:
        print('Request failed!')
        sys.exit(1)

    # parse the json
    data = json.loads(r.text)

    # get the name and build data from the json
    name = data['name']
    buildData = data['data']

    # parse the build data as json
    buildData = json.loads(buildData)

    # for each build profile in builddata["profiles"] print the name and let the user choose which one to use
    print("Profiles:")
    for i in range(len(buildData["profiles"])):
        print(str(i) + ": " + buildData["profiles"][i]["name"])

    profile = int(input("Choose profile: "))
    buildData = buildData["profiles"][profile]

    profileName = buildData["name"]
    className = buildData["class"]

    #### Extract data ####
    items = {}
    # Extract items in kanais cube
    cube = {}
    cube["weapon"] = {"id": buildData["kanai"]["weapon"]}
    cube["armor"] = {"id": buildData["kanai"]["armor"]}
    cube["jewelry"] = {"id": buildData["kanai"]["jewelry"]}

    items["cube"] = cube

    # Extract equiped items and special gems
    equiped = {}
    standardGems = ["diamond", "emerald", "ruby", "topaz", "amethyst"]

    for slot, item in list(buildData["items"].items()):
        equiped[slot] = {}
        equiped[slot]["id"] = item["id"]
        equiped[slot]["gem"] = {}
        if "gems" in item.keys():
            for gem in item["gems"]:
                if isinstance(gem, list):
                    if isinstance(gem[0], str):
                        equiped[slot]["gem"]["name"] = gem[0]
                elif isinstance(gem, dict):
                    equiped[slot]["gem"]["id"] = gem["id"]

        # If no "gem" is empty, delete it
        if equiped[slot]["gem"] == {}:
            del equiped[slot]["gem"]

    items["equiped"] = equiped

    #### Translate item ids to item names ####
    # Load translation file
    with open("translations.json", "r", encoding="utf-8") as f:
        translation = json.load(f)

    # Translate cube items
    for slot, item in list(items["cube"].items()):
        for item_translation in translation["items"]:
            if item["id"] == item_translation["id"]:
                items["cube"][slot]["name"] = item_translation["name"]

    # Translate equiped items
    for slot, item in list(items["equiped"].items()):
        for item_translation in translation["items"]:
            if item["id"] == item_translation["id"]:
                items["equiped"][slot]["name"] = item_translation["name"]
            elif "gem" in item.keys():
                if "id" in item["gem"].keys():
                    if item["gem"]["id"] == item_translation["id"]:
                        items["equiped"][slot]["gem"]["name"] = item_translation["name"]
                elif "name" in item["gem"].keys():
                    items["equiped"][slot]["gem"]["id"] = translation["legendaryGems"][item["gem"]["name"]]["id"]
                    items["equiped"][slot]["gem"]["name"] = translation["legendaryGems"][item["gem"]["name"]]["name"]

    #### Generate url for each item ####
    items_list = []
    baseURL = "https://eu.diablo3.blizzard.com/en-us/item/"
    for item_or_gem in [item for item in items["cube"].values()] + [item for item in items["equiped"].values()] + [gem for gem in [items["equiped"][slot]["gem"] for slot in items["equiped"].keys() if "gem" in items["equiped"][slot].keys()]]:
        sanitized_name = item_or_gem["name"].replace(
            "-", "").replace(" ", "-").replace("'", "")
        url = baseURL + sanitized_name.lower() + "-" + \
            handle_special_ids(item_or_gem["id"])
        item_or_gem["url"] = url
        items_list.append(item_or_gem)

    #### Check each url to see if it is valid ####
    # print("Checking urls...")
    # for item in items_list:
    #     r = requests.get(item["url"])
    #     if r.status_code != 200:
    #         print("Invalid url: " + item["url"])

    #### Generate bookmark  dict ####
    # load cached tags from json file
    with open("tags.json", "r", encoding="utf-8") as f:
        tags = json.load(f)

    # make user tag each item with a category (craft, bounty, gems, cube/gamble)
    print("Craft: 1")
    print("Bounty: 2")
    print("Gems: 3")
    print("Cube/Gamble: 4")
    print("Skip: 5")
    for item in items_list:
        # apply cached tags if available
        if item["id"] in tags.keys():
            item["category"] = tags[item["id"]]
            continue
        else:
            # keep asking until user enters a valid category
            while "category" not in item.keys():
                print("\r"+item["name"] + ": ", end="")
                category = int(input())
                if category == 1:
                    item["category"] = "craft"
                elif category == 2:
                    item["category"] = "bounty"
                elif category == 3:
                    item["category"] = "gems"
                elif category == 4:
                    item["category"] = "cube/gamble"
                elif category == 5:
                    item["category"] = "skip"

            # cache the tag
            tags[item["id"]] = item["category"]

    # save the cached tags to json file
    with open("tags.json", "w", encoding="utf-8") as f:
        json.dump(tags, f, indent=4)

    # load gambling costs from json file
    with open("gambleChances.json", "r", encoding="utf-8") as f:
        gambling = json.load(f)

    # calculate bloodshard and death breath costs
    for item in items_list:
        for item_gambling_chances in gambling[className]:
            if item["id"] == item_gambling_chances["id"]:
                # https://maxroll.gg/d3/d3-gamble-calculator
                # avarage_cost = (cost * 10) / chance
                # db_cost = 25 / uchance
                item["bloodshard_cost"] = math.ceil(
                    (item_gambling_chances["cost"] * 10) / item_gambling_chances["chance"])
                item["death_breath_cost"] = math.ceil(
                    25 / item_gambling_chances["uchance"])

    craft = {}
    craft["type"] = "folder"
    craft["name"] = "Craft"
    craft["children"] = [{"type": "url", "name": item["name"], "url": item["url"]}
                         for item in items_list if item["category"] == "craft"]

    bounty = {}
    bounty["type"] = "folder"
    bounty["name"] = "Bounty"
    bounty["children"] = [
        {"type": "url", "name": item["name"], "url": item["url"]} for item in items_list if item["category"] == "bounty"]

    gems = {}
    gems["type"] = "folder"
    gems["name"] = "Gems"
    gems["children"] = [{"type": "url", "name": item["name"], "url": item["url"]}
                        for item in items_list if item["category"] == "gems"]

    cube_gamble = {}
    cube_gamble["type"] = "folder"
    cube_gamble["name"] = "Cube/Gamble"
    cube_gamble["children"] = [
        {"type": "url", "name": f"{item['name']} - {item['bloodshard_cost']} - {item['death_breath_cost']}", "url": item["url"]} for item in items_list if item["category"] == "cube/gamble"]

    cube_gamble["children"].sort(key=lambda x: int(x["name"][x["name"].find(
        " - ")+3:x["name"].find(" - ", x["name"].find(" - ")+3)-2]))
    print(cube_gamble["children"])

    bookmark_items = {}
    bookmark_items["type"] = "folder"
    bookmark_items["name"] = "Items"
    bookmark_items["children"] = [craft, bounty, gems, cube_gamble]

    #### Write bookmarks to chrome bookmarks file ####
    appdata_local_path = os.getenv('LOCALAPPDATA', "")
    chrome_bookmarks_path = appdata_local_path + \
        "\\Google\\Chrome\\User Data\\Default\\Bookmarks"

    # read the bookmarks file
    with open(chrome_bookmarks_path, "r", encoding="utf-8") as f:
        bookmarks_file = json.load(f)

    # add the bookmarks
    for bookmark in bookmarks_file["roots"]["bookmark_bar"]["children"]:
        if bookmark["name"] == "Diablo strats":
            bookmark["children"].append(bookmark_items)

    # write the bookmarks file
    with open(chrome_bookmarks_path, "w", encoding="utf-8") as f:
        json.dump(bookmarks_file, f, indent=4)

    #### Save items to json file ####
    # format the json
    buildData = json.dumps(items, indent=4)

    # get the output file name
    if output == None:
        output = name.replace(" ", "_") + \
            "(" + profileName.replace(" ", "_") + ")"'.json'

    # save the build data as a json file
    with open(output, 'w') as f:
        f.write(buildData)


if __name__ == "__main__":
    #### Parse arguments ####
    # parse the command line arguments
    parser = argparse.ArgumentParser(
        description='Extracts the build data from a d3planner url.')
    parser.add_argument('url', metavar='url', type=str,
                        help='the d3planner url')
    parser.add_argument('--output', metavar='output',
                        type=str, help='the output file name')
    args = parser.parse_args()

    # get the url from the command line arguments
    url = args.url

    # get the output file name from the command line arguments
    output = args.output

    # check if the url is valid
    if not re.match(r'^https://maxroll\.gg/d3/d3planner/\d+(#.*)?$', url):
        print('Invalid url!')
        sys.exit(1)  # exit with error code 1
    main(url, output)
#### Save items to bookmarks ####
