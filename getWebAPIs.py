import requests
from bs4 import BeautifulSoup
import os
import argparse
from urllib.parse import urljoin
import pandas as pd
import json

# spracovať output file
# načítať stránku
# hrefy do dictionary {"meno API", "URL", "flagy"}

URL = "https://developer.mozilla.org/en-US/docs/Web/API"

APIS = []


def labelBySection(sections, sectionName):
    global APIS
    if not sectionName in ["see_also", None]:
        for li in sections.findAll("li"):
            name = li.find("a").text
            href = urljoin(URL, li.find("a").get("href"))

            spans = li.findAll("abbr", {"class": "icon"})
            span_names = " & ".join([str(i.get("title")) for i in spans])
            APIS.append({"API_name": name, "href": href, "section_name": sectionName, "attributes": span_names})


def getApis(exportDataframe=True):
    # get the data with
    data = requests.get(URL)
    if data.status_code == 200:
        soup = BeautifulSoup(data.text, "html.parser")
        sections = soup.findAll("section")
        for section in sections:
            labelBySection(section, section.get("aria-labelledby"))
        print("Number of APIs: ", len(APIS))
        df = pd.DataFrame.from_records(APIS)
        if exportDataframe:
            return df
        else:
            df.to_csv("webAPI-firefox.csv", ',')
        # print(df["attributes"].value_counts())


def getDetails(name, api_json):
    name = name.split(".")[-1]
    for feature in api_json["features"]:
        if name in feature["name"]:
            return feature
    return None

def getDanger(name, df_analysis):
    if name in df_analysis["func_name"].values:
        return df_analysis[df_analysis["func_name"] == name]["percentage"].values[0]
    return None

def getWrappStatus(name, jsonImplemented):
    for obj in jsonImplemented:
        for key in obj:
            if name in obj[key]:
                return True
    return False

def combineSources(allApis, uniqueApis, mozillaFolder, analysisData, implementedData):
    if not os.path.isdir(mozillaFolder):
        print(f"Wrong mozilla api folder {mozillaFolder}, generate one with 'python3 mergeData.py -ga WEB_apis'")
        return
    if not os.path.isfile(allApis):
        print(f"Wrong all apis file {allApis}")
        return
    if not os.path.isfile(uniqueApis):
        print(f"Wrong unique apis file {uniqueApis}")
        return

    df_unique = pd.read_json(uniqueApis)
    jsonAll = json.load(open(allApis))
    df_analysis = pd.read_json(analysisData)
    jsonImplemented = json.load(open(implementedData))
    final = {}
    # for each unique search for record in all and combine with data in mozilla folder and analysis
    temp_match = {}
    for index, row in df_unique.iterrows():
        name = row["func_name"]
        name_split = name.split(".")[0]
        # find in all
        temp_match[name] = {'API': "", 'sure': False, 'apis': [], "catId": ""}
        for api in jsonAll:
            for function in jsonAll[api]['features']:
                function_split = function.split(".")[0]
                if function == name:
                    temp_match[name]['API'] = api
                    temp_match[name]['sure'] = True
                    temp_match[name]['catId'] = jsonAll[api]['catId']
                    break
                elif function_split == name_split:
                    temp_match[name]['apis'].append(api)
        # search for deatails in mozilla folder
        if os.path.isfile(os.path.join(mozillaFolder, name_split + ".json")):
            api_json = json.load(open(os.path.join(mozillaFolder, name_split + ".json")))

        # get percentage of blocked apis
        if name in df_analysis["func_name"].values:
            temp_match[name]['percentage'] = df_analysis[df_analysis["func_name"] == name]["percentage"].values[0]
        # save to final
        try:
            feature = getDetails(name, api_json)
        except Exception as ex:
            feature = None
        danger = getDanger(name, df_analysis)
        isWrapped = getWrappStatus(name, jsonImplemented)
        if not temp_match[name]['API'] and temp_match[name]['sure']:
            # get most used from apis
            temp_match[name]['API'] = max(set(temp_match[name]['apis']), key=temp_match[name]['apis'].count)
        if temp_match[name]['API'] == "":
            temp_match[name]['API'] = "Unknown"
        if not temp_match[name]['API'] in final:
            final[temp_match[name]['API']] = {
                "API_class": temp_match[name]['API'],
                "API_name": api_json['info']['origId'],
                "Description": api_json['info']['description'],
                "URL": api_json['info']['url'],
                "catId": temp_match[name]['catId'] if temp_match[name]['catId'] != "" else "Unknown",
                "Features": [{
                    "name": name,
                    "description": feature['description'] if feature else None,
                    "url": feature['url'] if feature else None,
                    "type": feature['type'] if feature else None,
                    "catId": temp_match[name]['catId'] if temp_match[name]['catId'] != "" else "Unknown",
                    "danger": danger if danger else None,
                    "wrapped": isWrapped,
                }],
            }
        else:
            final[temp_match[name]['API']]['Features'].append({
                "name": name,
                "description": feature['description'] if feature else None,
                "url": feature['url'] if feature else None,
                "type": feature['type'] if feature else None,
                "catId": temp_match[name]['catId'] if temp_match[name]['catId'] != "" else "Unknown",
                "danger": danger if danger else None,
                "wrapped": isWrapped,
            })
    # save to json
    with open(f"final.json", "w") as f:
        json.dump(final, f, indent=4)




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-ga", "--get_apis",
                        help="Program will download all apis on developer.mozilla.org/en-US/docs/Web/API",
                        action="store_true")
    parser.add_argument("-aa", "--all_apis", help="All apis in json file from web api manager")
    parser.add_argument("-un", "--unique_apis", help="Unique apis in json file from analysis")
    parser.add_argument("-F", "--mozilla_folder", help="Folder with app apis from mozilla")
    parser.add_argument("-a", "--analysis", help="File with analysis data containing func_name and % of blocked apis")
    parser.add_argument("-i", "--implemented", help="File with json file containing implemented apis")
    parser.add_argument("-o", "--output", help="Output directory")
    args = parser.parse_args()
    if args.get_apis:
        getApis(False)
    elif args.all_apis and args.unique_apis and args.mozilla_folder and args.analysis and args.implemented and args.output:
        combineSources(args.all_apis, args.unique_apis, args.mozilla_folder, args.analysis, args.implemented, args.output)
    else:
        print("Wrong arguments")