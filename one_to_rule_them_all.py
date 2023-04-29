import argparse
import os
import sqlite3, json
import zipfile
from sys import stderr
import pandas as pd
import time
import shutil
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from string import Template
from matplotlib import pyplot as plt

# input will be DB with apis table

URL = "https://developer.mozilla.org/en-US/docs/Web/API"
APIS = []

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'sk,cs;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://developer.mozilla.org/en-US/docs/Web/API',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}

def time_it(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            print(f"Function {func.__name__} got an exception {e}.")
            return None
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time} seconds to run.")
        return result

    return wrapper


@time_it
def create_combined(db):
    print("Creating combined table")
    conn = sqlite3.connect(db)
    try:
        df = pd.read_sql_query(
            f"SELECT tranco, func_name, top_level_url, url, SUM(cnt) AS cnt, mode FROM apis GROUP BY tranco, func_name, top_level_url, url, mode",
            conn)

        df0 = df[df['mode'] == 0]
        df0['mode0cnt'] = df0['cnt']
        # df.loc[df['mode'] == 0, 'mode0cnt'] = df.loc[df['mode'] == 0, 'cnt']

        # remove column cnt and mode
        df0 = df0.drop(columns=['cnt', 'mode'])
        df1 = df[df['mode'] == 1]
        df1['mode1cnt'] = df1['cnt']
        df1 = df1.drop(columns=['cnt', 'mode'])
        # merge the two tables on the column tranco and func_name and sum cnt column
        dfcombined = pd.merge(df0, df1, on=['tranco', 'func_name', 'top_level_url', 'url'])
        dfcombined['mode0cnt'] = dfcombined.apply(
            lambda x: x['mode0cnt'] + (x['mode1cnt'] - x['mode0cnt']) if x['mode1cnt'] > x['mode0cnt'] else x[
                'mode0cnt'], axis=1)
        dfcombined['blocked'] = dfcombined['mode0cnt'] - dfcombined['mode1cnt']

        # save the merged table into the database
        dfcombined.to_sql("combined", conn, if_exists='replace', index=False)
        print(f"\t combined table created inside the {db}")
    except Exception as e:
        print(f"ERROR (create_combined) - {e}", file=stderr)
    finally:
        conn.close()


@time_it
def addAPICLass(db, allAPIS):
    print("Creating combined api table")
    try:
        # load all apis
        jsonAll = json.load(open(allAPIS))
        temp_match = {}
        for api in jsonAll:
            for func_name in jsonAll[api]['features']:
                if not func_name in temp_match:
                    temp_match[func_name] = {
                        "API": api,
                    }
                else:
                    print(f"Duplicate {func_name} in {api} and {temp_match[func_name]['API']}")

        # load aggregated database
        conn = sqlite3.connect(db)
        df = pd.read_sql("SELECT * FROM combined", conn)
        # add column api where func_name is in some of the jsonAll value['features']
        df['api'] = df['func_name'].apply(lambda x: temp_match[x]['API'] if x in temp_match else "Unknown")
        # save to database
        df.to_sql("combined_api", conn, if_exists="replace", index=False)
        print(f"\t combined_api table created inside the {db}")
    except Exception as e:
        print(f"ERROR (addAPIClass) - {e}", file=stderr)
    finally:
        conn.close()


@time_it
def create_statistics(db_name):
    print("Creating combined api grouped tables")
    dangerThreshold = 0.1 # consider only those with more than 10% of blocked requests
    try:
        conn = sqlite3.connect(db_name)
        df = pd.read_sql("SELECT * FROM combined_api", conn)


        # group by func_name and api, sum mode0cnt and mode1cnt
        df = df.groupby(['func_name', 'api']).agg(
            {'mode0cnt': 'sum',
             'mode1cnt': 'sum',
             'blocked': 'sum',
             'top_level_url': 'nunique'
             }).reset_index()
        df["percentage"] = ((df["mode0cnt"] - df["mode1cnt"]) / df["mode0cnt"])
        # remove all with percentage less than dangerThreshold
        df['dangerous_flag'] = df['percentage'] >= dangerThreshold
        df.to_sql("combined_api_grouped", conn, if_exists="replace", index=False)
        print(f"\t combined_api_grouped table created inside the {db_name}")

        df.to_excel("combined_api_grouped.xlsx", index=False)
        print(f"\t combined_api_grouped.xlsx created")

        df = df.groupby(['api']).agg(
            {'mode0cnt': 'sum',
             'mode1cnt': 'sum',
             'func_name': 'nunique',
             'dangerous_flag': 'sum',
             'blocked': 'sum',
             'top_level_url': 'sum'
             }).reset_index()
        # df['average_block_percentage'] = round(df['percentage'] / df['func_name'], 4)
        df["percentage"] = df["mode1cnt"] / df["mode0cnt"]
        all_urls = df['top_level_url'].sum()
        print(f"Total number of urls: {all_urls}")
        df['percentage_from_all'] = round((df['top_level_url'] / all_urls), 4)
        df['danger'] = (df['blocked']/df['mode0cnt'])*(df['dangerous_flag']/df['func_name'])*(df['top_level_url']/all_urls)
        df.to_sql("by_grouped_api", conn, if_exists="replace", index=False)
        print(f"\t by_grouped_api table created inside the {db_name}")
        df.to_excel("by_grouped_api.xlsx", index=False)
        print(f"\t by_grouped_api.xlsx created")
    except Exception as e:
        print(f"ERROR (create_statistics) - {e}", file=stderr)
    finally:
        conn.close()


@time_it
def topApisJSON(db_name):
    print("Creating top apis json")
    try:
        conn = sqlite3.connect(db_name)
        n = 1000
        query = f"SELECT DISTINCT func_name FROM combined"
        unique_apis = pd.read_sql_query(query, conn)

        # compare with unique in apis table
        query = f"SELECT DISTINCT func_name FROM apis"
        unique_apis_apis = pd.read_sql_query(query, conn)

        # combine both tables and remove duplicates
        unique_apis = pd.concat([unique_apis, unique_apis_apis]).drop_duplicates()
        # save to file
        unique_apis.to_json('unique_apis.json', orient='records')
        print(f"\t unique_apis.json created")

        # most blocked
        # query = f"SELECT func_name, SUM(mode0cnt), SUM(mode1cnt) FROM combined GROUP BY func_name ORDER BY SUM(mode1cnt) DESC LIMIT {n}"
        query = f"SELECT func_name, SUM(mode0cnt), SUM(mode1cnt), SUM(mode0cnt) - SUM(mode1cnt) as cnt_diff FROM combined GROUP BY func_name ORDER BY cnt_diff DESC LIMIT {n}"
        top_n_blocked = pd.read_sql_query(query, conn)
        # add percentage column
        top_n_blocked['percentage'] = 1 - (top_n_blocked['SUM(mode1cnt)'] / top_n_blocked['SUM(mode0cnt)'])
        # order by percentage
        top_n_blocked = top_n_blocked.sort_values(by=['percentage'], ascending=False)
        # save to file
        top_n_blocked.to_json('top_n_blocked.json', orient='records')
        print(f"\t top_n_blocked.json created")
    except Exception as e:
        print(f"ERROR (topApisJSON) - {e}", file=stderr)
    finally:
        conn.close()


# TEMPLATES
def wrapper_basic(function_, wrapped_name):
    function = function_.split(".")
    parent_object = '.'.join(function[:-1])
    parent_object_property = function[-1]
    wrapper = Template('''
    {
        parent_object: "$parent_object",
        parent_object_property: "$parent_object_property",
        wrapped_objects: [
            {
                original_name: "$function_",
                wrapped_name: "$wrapped_name",
            }
        ],
        wrapping_function_args: "...args",
        wrapping_function_body: `
                return null;
        `,
    },''')
    return wrapper.substitute(parent_object=parent_object, parent_object_property=parent_object_property,
                              function_=function_, wrapped_name=wrapped_name)


def generateWrapper_forGroup(apis: list):
    wrapper = Template('''
(function() {
	var wrappers = [
		$wrapper
	];
	add_wrappers(wrappers); // GENERATED
})();''')
    wrappers = ""
    for api in apis:
        api_wrapper = wrapper_basic(api, api.replace(".", ""))
        wrappers += f"{api_wrapper}"
    return wrapper.substitute(wrapper=wrappers)


def generateGroup(name_: str, label: str, description: str, wrappers: dict, description2=""):
    # NOTE wrappers will have at the first line // shortcut "AJAX" and at each line string in "",
    parsed_wrappers = ""
    description2_ = ""
    first = True
    for key, values in wrappers.items():
        if first:
            parsed_wrappers += f'// "{key}"\n'
            first = False
        else:
            parsed_wrappers += ('\t' * 3 + f'// "{key}"\n')
        for value in values:
            if values[-1] == value:
                parsed_wrappers += ('\t' * 3 + f'"{value}"')
            else:
                parsed_wrappers += ('\t' * 3 + f'"{value}",\n')

    description2_ = ""
    for name in description2:
        if description2[name]["description"] == None:
            fetched_description2 = ""
        else:
            fetched_description2 = " : " + description2[name]["description"].replace('"', "'").strip()
        description2_ += f'\t\t\t"{name}({description2[name]["danger"]}){fetched_description2}",\n'
    group = Template('''\t\t{
        name: "$name",
        label: "[API blocking] $label",
        description: "$description",
        description2: ["TheAPIs listed below are blocked because they were found to be used by fingerprinting scripts.",
$description2
        ],
        params: [
            {
                short: "Block",
                description: "Blocks the fingerprinting of $name by returning null.",
                config: [],
            },
        ],
        wrappers: [
            $wrappers
            ],
		},\n''')
    return group.substitute(name=name_.strip(), label=label.strip(),
                            description=description.replace('\n', ' ').replace('"', "'").strip(),
                            description2=description2_, wrappers=parsed_wrappers)

# settomgs = {apiname : {name: str, APIS:list, danger: fload, treshold: float}}
def generateLevel(settings: dict, level_name: str):
    # entry = f"""var {level_name} = {'{'}
    entry = f"""    "builtin": true,
	"level_id": L_EXPERIMENTAL,
	"level_text": "Experimental",
	"level_description": "Strict level protections with additional wrappers enabled (including APIs known to regularly break webpages and APIs that do not work perfectly). Use this level if you want to experiment with JShelter. Use Recommended or Strict level with active Fingerprint Detector for your regular activities.",
"""
    for api in settings:
        # if?
        # block = 1 if settings[api]["danger"] >= settings[api]["treshold"] else 0
        block = 1
        name = settings[api]["name"]
        entry += f'\t"{name}": {block},\n'
    # entry += "};"
    return entry


# TEMPLATES
# chceme vytvorit zaznamy pro kazdou API, ktera je wrappovaná a a musí obsahovať aj danger
def fillSettings(wholeAPI, average_treshold=0):
    totalLen = len(wholeAPI['Features']) if len(wholeAPI['Features']) != 0 else 1
    counter = 0
    for feature in wholeAPI['Features']:
        if not feature['wrapped']:
            counter += feature['danger']
    average = counter / totalLen
    block = 1 if average >= average_treshold else 0
    return {'block': block, 'totalLen': totalLen, 'counter': counter}


def generate_common(common_dir: str, final_json: str, treshold: int = None, autowrite:bool = True):
    if not os.path.exists(common_dir):
        print("The specified path does not exist.")
        exit(1)
    if not os.path.exists(final_json):
        print("The specified path does not exist.")
        exit(1)
    print("Generating common.js")
    # get all unimplemented apis
    finalJson = json.load(open(final_json, "r"))
    settings_ = {} # wrapped apis with danger
    for api in finalJson:
        # which are not implemented
        unimplemented_apis = []
        for feature in finalJson[api]["Features"]:
            if feature['danger'] == None:
                feature['danger'] = 0
            if treshold == None:
                unimplemented_apis.append(feature['name'])
            else:
                if not feature['wrapped'] and feature['danger'] >= treshold:
                    unimplemented_apis.append(feature['name'])
        # check if wrappingS-<api>.js exists
        if len(unimplemented_apis) == 0:
            continue
        # writing
        settings_[api] = {'name': f"{api}{finalJson[api]['catId']}", 'APIS': unimplemented_apis, 'danger': finalJson[api]['danger'], 'treshold': treshold}
        if not os.path.exists(f"{common_dir}/wrappingS-{api}.js"):
            text = generateWrapper_forGroup(unimplemented_apis)
            # names are api without .
            with open(f"{common_dir}/wrappingS-{api}.js", "w") as f:
                f.write(text)
        else:
            # check if the apis are already present
            generated = generateWrapper_forGroup(unimplemented_apis)
            with open(f"{common_dir}/wrappingS-{api}.js", "r") as f:
                if "// GENERATED" in f.read():
                    print(f"{api} - already present duplications may occur, please remove previously generated wrappers")
                    continue
                if generated in f.read():
                    print(f"{api} - already present")
                    continue
            # if it exists, append the unimplemented apis to it
            with open(f"{common_dir}/wrappingS-{api}.js", "a") as f:
                f.write(generateWrapper_forGroup(unimplemented_apis))

    # generate groups to levels.js at line with // INSERT-ANCHOR
    to_insert = ""
    for api in finalJson:
        wrappers_to_insert = {}
        description2_ = {}
        for feature in finalJson[api]["Features"]:
            if feature['danger'] == None:
                feature['danger'] = 0
            if treshold is None:
                treshold = -1 # always lower than 0
            if not feature['wrapped'] and feature['danger'] >= treshold:
                if not api in wrappers_to_insert:
                    wrappers_to_insert[api] = [feature['name']]
                else:
                    wrappers_to_insert[api].append(feature['name'])

                description2_[feature['name']] = {
                    "description": feature['description'],
                    "url": feature['url'],
                    # round danger to 2 decimal places
                    "danger": f"{round(feature['danger'] * 100, 2)} %"}
        wrapper_name = f"{finalJson[api]['API_class']}{finalJson[api]['catId']}"
        if not wrappers_to_insert == {}:
            to_insert += generateGroup(
                # name_=f"{finalJson[api]['catId']}",
                name_=wrapper_name,
                label=finalJson[api]['API_class'],
                description=finalJson[api]['Description'],
                wrappers=wrappers_to_insert,
                description2=description2_)
    with open(f"{common_dir}/WEBAPI_levels-{treshold}.js", "w", encoding="utf-8") as f:
        f.write(to_insert)
        print(f"\tWEBAPI_levels-{treshold}.js generated")

    # create dictionary from names and danger (asi average of all) and if >= than treshold assing 1, otherwise 0
    level = generateLevel(settings=settings_, level_name="Experimental")
    with open(f"{common_dir}/ExperimentalVar-{treshold}.js", "w", encoding="utf-8") as f:
        f.write(level)
        print(f"\tExperimentalVar-{treshold}.js generated")

    # add to_insert to levels.js at line with // INSERT-ANCHOR
    with open(f"{common_dir}/levels.js", "r", encoding="utf-8") as f:
        lines = f.read()

    to_write = ""
    if "// INSERT-ANCHOR" in lines:
        to_write = lines.replace("// INSERT-ANCHOR", f"// FROM\n{to_insert}// TO\n")
        print("\tlevels.js generated code at // INSERT-ANCHOR")
    elif "// FROM" in lines and "// TO" in lines:
        from_ = lines.index("// FROM")
        to_ = lines.index("// TO")
        to_write = lines[:from_] + f"// FROM\n{to_insert}" + lines[to_:]
        print("\tlevels.js generated code at // FROM ... // TO")
    else:
        to_write = lines
        print("Cannot find the anchor to insert the generated code, please insert it manually.\n",
              "The code from WEBAPI_levels.js should be manually inserted at the end of groups list.")

    if "// EXPERIMENTAL" in lines:
        to_write = to_write.replace("// EXPERIMENTAL", f"// EXPFROM \n{level}// EXPTO\n")
        print("\tlevels.js generated code at // EXPERIMENTAL")
    elif "// EXPFROM" in lines and "// EXPTO" in lines:
        from_ = to_write.index("// EXPFROM")
        to_ = to_write.index("// EXPTO")
        to_write = to_write[:from_] + f"// EXPFROM\n{level}" + to_write[to_:]
        print("\tlevels.js generated code at // EXPFROM ... // EXPTO")
    else:
        to_write = to_write
        print("Cannot find the anchor to insert the generated code, please insert it manually.\n",
              "The code from ExperimentalVar.js should be manually inserted at the end of levels list.")

    if autowrite:
        with open(f"{common_dir}/levels.js", "w", encoding="utf-8") as f:
            f.write(to_write)
    else:
        print("levels.js generated, but not written to file, please write it manually or add autowrite=True.")
        return (to_insert, lines, level, to_insert)

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


def getDescription(url: str) -> str:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print(f"\t Getting description from {url}")
        soup = BeautifulSoup(response.text, "html.parser")
        # find article with calss main-page-content
        article = soup.find("article", {"class": "main-page-content"})
        if article is not None:
            # get text content from first div and there from last <p>
            div = article.find("div")
            if div is not None:
                p = div.findAll("p")[-1].text.strip().replace("\n", " ")
                p = re.sub(' +', ' ', p)  # remove multiple whitespaces
            return p


def crawlAPIS(dataframe, filepath: str):
    stopper = 5
    for index, row in dataframe.iterrows():
        # if index == stopper:
        #     break
        try:
            print(index, row['href'])
            # get href content with headers
            data = requests.get(row['href'], headers=headers)
            if data.status_code == 200:
                soup = BeautifulSoup(data.text, "html.parser")
                main_url = urlparse(row['href']).scheme + "://" + urlparse(row['href']).netloc
                # find first <p> in main tag with id "content" where is not class "notecard"
                p = soup.find("main", {"id": "content"}).find("div", {'class': "section-content"}).findAll("p")[-1].text
                # p = soup.find("main", {"id": "content"}).find("div", {'class': "section-content"}).find("p")
                API_description = p

                # find section where aria-labelledby is "interfaces"

                features = {"features": []}
                rel_tops = soup.find("nav", {"aria-label": "Related Topics"})
                # search for <li class="toggle">
                if rel_tops is not None:
                    lis = rel_tops.findAll("li", {"class": "toggle"})
                    for li in lis:
                        # find <summary> and get text
                        summary = li.find("summary")
                        if summary is not None:
                            section_source = summary.text
                            # find all <li> in <ul> and get text
                            ul = li.find("ol")
                            if ul is not None:
                                lis = ul.findAll("li")
                                for li in lis:
                                    full_url = f"{main_url}{li.find('a')['href']}"
                                    description = getDescription(full_url)
                                    features['features'].append({
                                        "name": li.text,
                                        "description": description,
                                        "url": full_url,
                                        "type": section_source
                                    })

                entry = {"info":
                             {"id": index,
                              "origId": row['API_name'],
                              "name": row['API_name'],
                              "url": row['href'],
                              "catId": "TODO",
                              "description": API_description
                              }, "features": features['features']}
                print(f"{filepath}/{entry['info']['origId'].replace(' ', '_')}.json")
                with open(f"{filepath}/{entry['info']['origId'].replace(' ', '_')}.json", "w") as f:
                    f.write(json.dumps(entry, indent=4))
            else:
                print(f"ERROR (crawlAPIS) - {row['href']} is not accessible", file=stderr)
                continue
        except Exception as e:
            print(f"ERROR (crawlAPIS) - occurred at {index} {row['href']} - {e}", file=stderr)


def getMozilla(outDir="WEB_apis", headless=False):
    print("Downloading all the data from Mozilla (https://developer.mozilla.org/en-US/docs/Web/API)")
    # warning: this will delete the folder if it exists
    if not headless:
        inp = input(
            "Do you want to download all the data? It is time consuming process which will replace existing WEB_apis folder (y/n): ")
        if inp != "y":
            return 0
    if os.path.isdir(outDir):
        shutil.rmtree(outDir)
    os.mkdir(outDir)
    df_basic = getApis(exportDataframe=True)
    crawlAPIS(dataframe=df_basic, filepath=outDir)
    print(f"\t Succesfully generated {outDir} folder")


def getWrappStatus(name, jsonImplemented):
    for obj in jsonImplemented:
        for key in obj:
            if name in obj[key]:
                return True
    return False


def getDanger(name, df_analysis):
    if name in df_analysis["func_name"].values:
        return df_analysis[df_analysis["func_name"] == name]["percentage"].values[0]
    return None


def getDetails(name, api_json):
    name = name.split(".")[-1]
    for feature in api_json["features"]:
        if name in feature["name"]:
            return feature
    return None


def finalJSON(allAPIS, unique_apis, mozilla_folder, analysisData, implemented_data, db_name):
    print("Generating final json file")
    if not os.path.isdir(mozilla_folder):
        print(f"Wrong mozilla api folder {mozilla_folder}, generate one with 'python3 mergeData.py -ga WEB_apis'")
        return
    if not os.path.isfile(allAPIS):
        print(f"Wrong all apis file {allAPIS}")
        return
    if not os.path.isfile(unique_apis):
        print(f"Wrong unique apis file {unique_apis}")
        return
    if not os.path.isfile(db_name):
        print(f"Unable to find {db_name}")
        return

    conn = sqlite3.connect(db_name)
    df_cag = pd.read_sql_query("SELECT * FROM combined_api_grouped", conn)
    df_bga = pd.read_sql_query("SELECT * FROM by_grouped_api", conn)
    conn.close()
    df_unique = pd.read_json(unique_apis)
    jsonAll = json.load(open(allAPIS))
    df_analysis = pd.read_json(analysisData) # top n blocked
    jsonImplemented = json.load(open(implemented_data))
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
        if os.path.isfile(os.path.join(mozilla_folder, name_split + ".json")):
            api_json = json.load(open(os.path.join(mozilla_folder, name_split + ".json")))

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
        APIdanger = df_bga[df_bga["api"] == temp_match[name]['API']]["danger"].values[0] if temp_match[name]['API'] != "Unknown" and len(df_bga[df_bga["api"] == temp_match[name]['API']]["danger"]) != 0 else None
        APITLD = df_bga[df_bga["api"] == temp_match[name]['API']]["top_level_url"].values[0] if temp_match[name]['API'] != "Unknown" and len(df_bga[df_bga["api"] == temp_match[name]['API']]["top_level_url"]) != 0 else None
        if not temp_match[name]['API'] in final:
            final[temp_match[name]['API']] = {
                "API_class": temp_match[name]['API'],
                "API_name": api_json['info']['origId'],
                "Description": api_json['info']['description'],
                "URL": api_json['info']['url'],
                "catId": temp_match[name]['catId'] if temp_match[name]['catId'] != "" else "Unknown",
                "danger": APIdanger,
                "top_level_url": int(APITLD) if APITLD else None,
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
        print("Succesfully generated final.json file")


def all_apis(path, headless=False):
    print("Generating all_apis.json file")
    if not os.path.exists(path):
        print("The specified path does not exist.")
        exit(1)
    # warning
    if not headless:
        inp = input(
            "This will overwrite the all_apis.json file. The new file will not be able to parse all functions, resulting Unknow category API, do you want to continue? (y/n)")
        if inp != "y":
            print("Aborting")
            return
    apis = {}
    sources = []
    domains = []
    for file in os.listdir(path):
        if file.endswith(".json"):
            nameconvension = file.strip(".json")
            filepath = f"{path}/{file}"
            with open(filepath, "r") as f:
                content = json.load(f)
                if content["info"]["url"] not in sources:
                    domain = urlparse(content["info"]["url"]).netloc
                    sources.append(content["info"]["url"])
                    if not domain in domains:
                        domains.append(domain)
                apis[nameconvension] = {"catId": content['info']['catId'], "features": content["features"]}

    with open("sources.json", "w") as f:
        json.dump(sources, f, indent=4)
        print("\t sources.json file created")
    with open("all_apis.json", "w") as f:
        json.dump(apis, f, indent=4)
        print("\t all_apis.json file created")


def getImplementedApis(path):
    print("Getting already implemented apis")
    if not os.path.exists(path):
        print("The specified path does not exist.")
        exit(1)

    apis = []
    for file in os.listdir(path):
        if file.startswith("wrappingS") and file != "wrapping.js":
            filedetails = getDetailsFromFile(f"{path}/{file}")
            apis.append(filedetails)
    # save all apis to a json file
    with open(f"implemented_apis.json", "w") as f:
        json.dump(apis, f, indent=4)
        print("\t implemented_apis.json file created")
    return apis


def re_find_apis(file, file_contents):
    wrappers = {}
    po, pop = "", ""
    for line in file_contents:
        parent_object = re.findall(r'parent_object:.*"(.*)",', line)
        if parent_object:
            po = parent_object[0]
            continue
        parent_object_poperty = re.findall(r'parent_object_property:.*"(.*)",', line)
        if parent_object_poperty:
            pop = parent_object_poperty[0]
            if file in wrappers:
                if f"{po}.{pop}" not in wrappers[file]:
                    wrappers[file].append(f"{po}.{pop}")
            else:
                wrappers[file] = [f"{po}.{pop}"]
            po, pop = "", ""
            continue
    return wrappers


def getDetailsFromFile(file):
    # file name is 'wrappingS-ECMA-ARRAY.js' extract only ECMA-ARRAY using re
    s = re.findall(r'wrappingS-(.*)\.js', file)
    if s:
        filename = s[0]
    else:
        filename = file
    print(filename)
    with open(file, "r") as f:
        print("Reading file: " + file)
        content = re_find_apis(filename, f.readlines())
        # print(content)
        # print(con
    return content


def getRepositories(repos: list):
    for repo in repos:
        print(f"Getting {repo}")
        os.system(f"git clone {repo}")


def getByTreshold(db_name, treshold: int):
    conn = sqlite3.connect(db_name)
    df_c = pd.read_sql_query("SELECT * FROM combined_api_grouped", conn)
    df = df_c[df_c['percentage'] >= treshold]
    conn.close()
    return df

def generate_graphs(db_name):
    conn = sqlite3.connect(db_name)
    df_c = pd.read_sql_query("SELECT * FROM combined_api_grouped", conn)
    # najblokovaniejsie
    df = df_c.sort_values(by=['percentage'], ascending=False).head(10)
    df.plot.bar(x='func_name', y=['mode0cnt', 'blocked'], logy=True, figsize=(10, 8))
    plt.xlabel('API index', fontsize=10)
    plt.ylabel('Počet volaní jednotlivých API [log]')
    plt.legend(['Bez rozšírenia', 'Počet blokovaných volaní'])
    ax = plt.gca()
    ax.set_xticklabels(ax.get_xticks(), rotation=0)
    plt.savefig('top10.png', dpi=1000, bbox_inches='tight')
    plt.show()
    # save as png
    df.to_latex('top10.tex', index=False, caption="10 Najpoužívanejších API s rozšírením a bez neho", label="top10")
    # najpouzívanejsie
    df_n = df_c.sort_values(by=['mode0cnt'], ascending=False).head(10)
    df_n.plot.bar(x='func_name', y=['mode0cnt', 'blocked'], figsize=(10, 8))
    plt.xlabel('API index', fontsize=10)
    plt.ylabel('Počet volaní jednotlivých API [10 mil.]')
    plt.legend(['Bez rozšírenia', 'Počet blokovaných volaní'])
    ax = plt.gca()
    ax.set_xticklabels(ax.get_xticks(), rotation=0)
    plt.savefig('top10_used.png', dpi=1000, bbox_inches='tight')
    plt.show()
    df_n.to_latex('top10_used.tex', index=False, caption="10 Najpoužívanejších API s rozšírením a bez neho", label="top10_used")
    # save as png
    conn.close()
    # analyze API
    conn = sqlite3.connect(db_name)
    df = pd.read_sql_query("SELECT * FROM by_grouped_api", conn)
    # remove where danger = 0
    print("Danger = 0")
    print(df[df['danger'] == 0])
    print(len(df[df['danger'] == 0]))
    print("Danger != 0")
    df = df[df['danger'] != 0]
    # extract columns api, danger, mode0cnt, mode1cnt, func_name, top_level_url and dangerous_flag to latex
    dfe = df[['api', 'danger', 'mode0cnt', 'mode1cnt', 'func_name', 'top_level_url', 'dangerous_flag']]
    # round danger to 2 decimals
    dfe['danger'] = dfe['danger'].round(5)
    dfe = dfe.sort_values(by=['danger'], ascending=False)
    dfe.to_latex('by_grouped_api.tex', index=False, caption="APIs grouped by danger level", label="danger")

def compute_tresholds(db_name, tresholds):
    # treshold variations
    conn = sqlite3.connect(db_name)
    df_base = pd.read_sql_query("SELECT * FROM combined_api_grouped", conn)
    conn.close()

    # create dictionary with key api and value = blocked/mode0cnt
    df_base_apis_blocked_ratio = df_base.groupby('api').apply(lambda x: x['blocked'].sum() / x['mode0cnt'].sum()).to_dict()
    df_base_function_count = df_base.groupby('api').apply(lambda x: len(x['func_name'].unique())).to_dict()
    allurls = 2973276
    out = {}
    for t in tresholds:
        df = getByTreshold(db_name, t)
        # get number of functions for each api
        func_names_for_treshold = df.groupby('api').apply(lambda x: len(x['func_name'].unique())).to_dict()
        # result will be json with key = api and value = {func = func_name, danger = percentage }
        # sum of top_level_url for each api
        df_urls = df.groupby('api').apply(lambda x: x['top_level_url'].sum()).to_dict()
        result = {}
        # compute danger for each api
        for api in df['api'].unique():
            if api in out:
                out[api].append({
                    "treshold": t,
                    "danger": (df_base_apis_blocked_ratio[api])*(func_names_for_treshold[api]/df_base_function_count[api])*(df_urls[api]/allurls),
                    "funcs": func_names_for_treshold[api],
                    "urls": df_urls[api]})
            else:
                out[api] = [{
                    "treshold": t,
                    "danger": (df_base_apis_blocked_ratio[api])*(func_names_for_treshold[api]/df_base_function_count[api])*(df_urls[api]/allurls),
                    "funcs": func_names_for_treshold[api],
                    "urls": df_urls[api]}]

        for index, row in df.iterrows():
            if row['api'] in result:
                result[row['api']].append({'func': row['func_name'], 'danger': row['percentage']})
            else:
                result[row['api']] = [{'func': row['func_name'], 'danger': row['percentage']}]
        if not os.path.isdir("tresholds"):
            os.mkdir("tresholds")
        with open(f"tresholds/treshold_{t}.json", "w") as f:
            json.dump(result, f, indent=4)
    # save outapi to json
    with open(f"tresholds-out.json", "w") as f:
        json.dump(out, f, indent=4)
    # load all apis into one dataframe
    dataframe = pd.DataFrame()
    for api in out:
        for t in out[api]:
            dataframe = dataframe.append({"api": api, "treshold": t['treshold'], "danger": t['danger'], "funcs": t['funcs'], "urls": t['urls']}, ignore_index=True, )
    dataframe = dataframe.sort_values(by=['danger'], ascending=False)
    # get top 10 most used apis
    top10 = dataframe.groupby('api').apply(lambda x: x['urls'].sum()).sort_values(ascending=False).head(5).index.tolist()
    # get top 10 most blocked apis which has entries in most tresholds
    top10_blocked = dataframe.groupby('api').apply(lambda x: len(x['treshold'].unique())).sort_values(ascending=False).head(5).index.tolist()
    # combine top10 and top10_blocked
    top10 = list(set(top10 + top10_blocked))
    # create graph where top 10 most used apis (has most urls) will have different colour showing danger in logarithmic scale and funcs for each treshold
    fig, ax = plt.subplots()
    fig.set_size_inches(8, 5)
    for api in top10:
        df = dataframe[dataframe['api'] == api]
        df.sort_values(by=['treshold'], inplace=True)
        plt.plot(df['treshold'], df['danger'], label=api)
    plt.legend()
    plt.yscale('log')
    plt.xlabel('Treshold')
    plt.ylabel('Danger [log.]')
    # plt.title('Danger for top 5 most dangerous APIs')
    plt.savefig('tresholds.png', dpi=1000, bbox_inches='tight')
    plt.show()

    print(dataframe)


def getTopNBlocked(db_name, n):
    conn = sqlite3.connect(db_name)
    df = pd.read_sql_query("SELECT * FROM combined_api", conn)
    # group by url and sum blocked and mode0cnt. Also add another column with list of unique apis and list of unique func_name
    df = df.groupby('url').agg({'blocked': 'sum', 'mode0cnt': 'sum', 'api': lambda x: list(x.unique()), 'func_name': lambda x: list(x.unique())})
    df = df.sort_values(by=['blocked'], ascending=False)

    conn.close()
    return df.head(n)


def main(db_name, headless=False):
    # try:
    # get Web APIs from mozilla
    # getMozilla("WEB_apis", headless=headless)
    #
    # # clone git repositories
    getRepositories(["https://github.com/pes10k/web-api-manager.git", "https://pagure.io/JShelter/webextension.git"])
    #
    # # # get all apis
    # all_apis("web-api-manager/sources/standards", headless=headless)


    # create or replace combined table and fix the difference between mode0 and mode1 cnts
    # create_combined(db_name)
    # #
    # # # create combined api table
    # addAPICLass(db_name, "all_apis.json")
    #
    # # create combined api grouped tables and save them to excel
    # create_statistics(db_name)
    # topApisJSON(db_name)

    # generate_graphs(db_name)
    # generate tresholds with step of 0.01

    # tresholds = [round(x * 0.01, 2) for x in range(0, 101)]
    # compute_tresholds(db_name, tresholds) # graph

    # # implemented apis
    # getImplementedApis("webextension/common/")
    #
    #
    # # genenrate final json
    # finalJSON(
    #     allAPIS="all_apis.json",
    #     unique_apis="unique_apis.json",
    #     mozilla_folder="WEB_apis",
    #     analysisData="top_n_blocked.json",
    #     implemented_data="implemented_apis.json",
    #     db_name=db_name)
    #
    # generate_common("webextension/common", "final.json", treshold=None)
    # #################################### TESTING ########################################
    # for treshold in [0.2, 0.25, 0.3, 0.35, 0.4]:
    #     (to_insert, lines, level, to_write) = generate_common("webextension/common", "final.json", treshold=treshold, autowrite=False)
    #     # print(f"Lines: {lines}, level: {level}")
    #     if not os.path.isdir("tresholds"):
    #         os.mkdir("tresholds")
    #     with open(f"tresholds/levels-{treshold}.js", "w", encoding="utf-8") as f:
    #         f.write(to_write)
    #
    # # get urls with most blocked apis
    # urls = getTopNBlocked(db_name, 20)
    # urls.to_excel("top20.xlsx")
    # print(urls)

    # replace common directory
    shutil.rmtree("webextension/common")
    # unzip "common.zip" into "webextension"
    with zipfile.ZipFile("common.zip", 'r') as zip_ref:
        zip_ref.extractall("webextension")


    generate_common("webextension/common", "final.json", treshold=0.4, autowrite=True)

    # except Exception as e:
    #     print(f"ERROR - {e}", file=stderr)
    # finally:
    #     print("DONE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generates json files from database')
    parser.add_argument('-db', help='Path to the database sqlite file')
    parser.add_argument('--headless', help='Headless downloading', action="store_true")
    args = parser.parse_args()

    if args.db:
        if os.path.isfile(args.db) and args.db.endswith(".sqlite"):
            main(args.db, args.headless)
        else:
            print("Database file does not exist")
