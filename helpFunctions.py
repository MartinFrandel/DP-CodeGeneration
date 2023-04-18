import logging
import os
import sqlite3
import zipfile
from builtins import str
import time
from urllib.parse import urlparse
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas
import re
import numpy as np
import pandas as pd
import getWebAPIs
import requests
from bs4 import BeautifulSoup

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
################### Crawling Web API ##################

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
                p = re.sub(' +', ' ', p) # remove multiple whitespaces
            return p

# goes throug all href links in dataframe, and adds to dataframe Web APIS, description,
def crawlAPIS(dataframe: pandas.DataFrame, logger: logging.Logger, filepath: str):
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
                API_description = ""
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
                        {
                            "id": index,
                            "origId": row['API_name'],
                            "name": row['API_name'],
                            "url": row['href'],
                            "catId": "TODO",
                            "description": API_description # TODO
                        }, "features": features['features']}
                print(f"{filepath}/{entry['info']['origId'].replace(' ', '_')}.json")
                with open(f"{filepath}/{entry['info']['origId'].replace(' ', '_')}.json", "w") as f:
                    f.write(json.dumps(entry, indent=4))
            else:
                logger.warning(f"crawlAPIS: {row['href']} is not accessible")
                continue
        except Exception as e:
            logger.warning(f"crawlAPIS: ERROR occurred at {index} {row['href']} - {e}")


#######################################################

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


def getFolderSize(foldername: str) -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(foldername):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size


def isZip(filename: str) -> bool:
    if zipfile.is_zipfile(filename):
        return True
    return False


def findOneByExtension(directory: str, extension: str, logger: logging.Logger) -> str:
    for file in os.listdir(directory):
        if file[-(len(extension)):] == extension:
            return f"{directory}/{file}"
    logger.warning(f"findOneByExtension: {directory} {extension} NOT FOUND ANY CORRESPONDING FILE!!")
    return None


def findManyByExtension(directory: str, extension: str, logger) -> list:
    response = []
    for file in os.listdir(directory):
        if file[-(len(extension)):] == extension:
            response.append(f"{directory}/{file}")
    if response == []:
        logger.warning(f"findOneByExtension: {directory} {extension} NOT FOUND ANY CORRESPONDING FILE!!")
    return response


def setLogger(filename: str):
    # Logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # vytvorenie handlera pre zápis logov do konzoly
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # vytvorenie handlera pre zápis logov do súboru
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(logging.DEBUG)

    # vytvorenie formátovacieho stringu pre logy
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # priradenie formátovacieho stringu k handlerom
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # pridanie handlerov k loggeru
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # logger.debug("This is a debug message.")
    # logger.info("This is an info message.")
    # logger.warning("This is a warning message.")
    # logger.error("This is an error message.")
    # logger.critical("This is a critical message.")
    return logger


def checkDirectory(filepath: str) -> bool:
    if os.path.isdir(filepath):
        return True
    else:
        print(f"ERROR - Not valid directory ({filepath})")
        exit()


def checkExtension(filename: str, extension: str) -> bool:
    return filename[-len(extension):] == extension


########################## Analyza dat ##################################


def savePlotsAndTables(plot=None, functionName="default", OutputDirectory="default", table=""):
    o_dir = f"{OutputDirectory}/{functionName}"
    if not (os.path.isdir(o_dir)):
        os.makedirs(o_dir)

    if not table == "":
        with open(f"{o_dir}/{functionName}-latex.txt", 'w') as fd:
            fd.write(table)

    if plot != None:
        plot.savefig(f"{o_dir}/{functionName}-graph.png")


# TODO tabulka najpoužívanejšie API a porovnať s predchádzajúcim typom a tabulkou 23312/5.1
# to isté z rozšírením a bez neho - plus sa pozrieť na rozdiel

def mostUsedAPIs(df, mode):
    # Group the data by func_name and sum the values in the cnt column for both mode 1 and mode 0
    # TODO bacha na to kde je viac s rozšírením - nedostatok dát
    # mode 0 je normal a mode 1 je s rozsirenim
    df_grouped = df.groupby(['func_name', 'mode'])['cnt'].sum()

    # Unstack the data so that each mode is a separate column
    df_unstacked = df_grouped.unstack()

    if mode:
        df_unstacked['diff'] = round(100 - (df_unstacked[1] / df_unstacked[0] * 100), 2)

        # Sort the values in descending order
        df_sorted = df_unstacked.sort_values(by='diff', ascending=False)
    else:

        # Sort the values in descending order
        df_sorted = df_unstacked.sort_values(by=0, ascending=False)

    # Get the top 10 func_names
    top_10 = df_sorted[:10]

    # Plot the top 10 func_names as a stacked bar chart
    plt.figure(figsize=(10, 8))
    if mode:
        top_10[[0, 1]].plot(kind='bar', stacked=False, log=True)
    else:
        top_10[[0, 1]].plot(kind='bar', stacked=False, log=False)
    plt.title(f'{"10 Najpoužívanejších API s rozšírením a bez neho" if not mode else "10 Najblokovanejších API rozšírením"}')
    plt.xlabel('API index', fontsize=10)
    plt.ylabel(f'Počet volaní jednotlivých API{" [mil.]" if not mode else " [log]"}')

    plt.legend(['Bez rozšírenia', 'S rozšírením'])
    ax = plt.gca()
    ax.set_xticklabels(ax.get_xticks(), rotation=0)

    if mode:
        savePlotsAndTables(plot=plt, functionName="mostUsedAPIs_mode", OutputDirectory="graphs", table=top_10.style.to_latex())
    else:
        savePlotsAndTables(plot=plt, functionName="mostUsedAPIs", OutputDirectory="graphs", table=top_10.style.to_latex())
    plt.show()


# TODO počty za celkové stránky z rozšírením a bez neho (preložené do jedného grafu)
def impactOfExtensionOnAPIsThroughTranco(df, option):
    # Group the data by tranco and mode and sum the cnt values

    df_agg = df.groupby(['tranco', 'mode'])['cnt'].sum().reset_index()

    # Group the data by tranco and mode and calculate the median of the cnt values
    # df_agg = df.groupby(['tranco', 'mode'])['cnt'].median().reset_index()

    # Create a pivot table with the tranco values as the index, the mode values
    # as the columns, and the cnt values as the values
    df_pivot = df_agg.pivot(index='tranco', columns='mode', values='cnt')
    df_pivot = df_pivot.dropna(how='any').sort_index()

    x = df_pivot.index

    fig, ax = plt.subplots()
    ax.scatter(x, df_pivot[0], label="Bez rozšírenia", color='blue', marker='x')
    ax.scatter(x, df_pivot[1], label="S rozšírením", color='red', marker='o', facecolor='none')

    rows = int(str(df_pivot.shape[0])[:2])
    plt.xticks(df_pivot.index[::rows], df_pivot.index[::rows])
    ax.set_ylim(0, df_pivot[0].max())
    ax.set_xlim(0, x.max())
    # Add a legend
    plt.legend()
    plt.title('Celkové počty zaznamenaných API s rozšírením a bez neho')

    # Add labels
    plt.xlabel('Tranco')
    plt.ylabel('Počet API')
    plt.tight_layout()
    savePlotsAndTables(plot=plt,
                       functionName="impactOfExtensionOnAPIsThroughTranco",
                       OutputDirectory="graphs",
                       table=df_pivot.style.to_latex())

    # Show the plot
    plt.show()



# TODO počty webových api bez rozšírenia na hlavnej stránke a na vedľajších,
#  optional : preložené grafom aj zo stránok s blokovaním a nejaká tabuľka rozdieľov v \%.
def webAPIonMainAndSidePages(df: pandas.DataFrame):

    pattern = re.compile(r'^https?:\/\/(www\.)?[^\/]+\.[^\/.]{2,3}(\/[a-z]{2})?\/?$')  # berie aj /en/ ako main page
    df.loc[:, 'is_main_page'] = df['top_level_url'].apply(lambda x: True if pattern.match(x) else False)
    # len mod 0
    df_mode_0 = df[df['mode'] == 0]
    df_mode_1 = df[df['mode'] == 1]

    fig, axes = plt.subplots(nrows=1, ncols=2)

    # získať na hlavnej
    df_main0 = df_mode_0[df_mode_0['is_main_page'] == True]
    df_main1 = df_mode_1[df_mode_1['is_main_page'] == True]
    df_side0 = df_mode_0[df_mode_0['is_main_page'] == False]
    df_side1 = df_mode_1[df_mode_1['is_main_page'] == False]

    df_main_cnt0 = df_main0.groupby('tranco')['cnt'].sum().reset_index()
    df_main_cnt1 = df_main1.groupby('tranco')['cnt'].sum().reset_index()
    df_side_cnt0 = df_side0.groupby('tranco')['cnt'].sum().reset_index()
    df_side_cnt1 = df_side1.groupby('tranco')['cnt'].sum().reset_index()

    main_sum0 = [df_main_cnt0['cnt'].sum(), df_main_cnt0.shape[0]]
    main_sum1 = [df_main_cnt1['cnt'].sum(), df_main_cnt1.shape[0]]
    side_sum0 = [df_side_cnt0['cnt'].sum(), df_side_cnt0.shape[0]]
    side_sum1 = [df_side_cnt1['cnt'].sum(), df_side_cnt1.shape[0]]

    axes[0].pie([main_sum0[0]/main_sum0[1], side_sum0[0]/side_sum0[1]], labels=["Hlavná stránka", "Vedlajšie"])
    axes[1].pie([main_sum1[0]/main_sum1[1], side_sum1[0]/side_sum1[1]], labels=["Hlavná stránka", "Vedlajšie"])
    axes[0].set_title(f"Bez rozšírenia", fontsize=12)
    axes[1].set_title(f"S rozšírením", fontsize=12)
    red_patch0 = mpatches.Patch(label=f'{round(main_sum0[0]/main_sum0[1], 2)}')
    red_patch1 = mpatches.Patch(label=f'{round(main_sum1[0]/main_sum1[1], 2)}')
    blue_patch0 = mpatches.Patch(color='orange', label=f'{round(side_sum0[0]/side_sum0[1], 2)}')
    blue_patch1 = mpatches.Patch(color='orange', label=f'{round(side_sum1[0]/side_sum1[1], 2)}')

    axes[0].legend(title="Priemerný počet API volaní",
                   handles=[red_patch0, blue_patch0],
                   bbox_to_anchor=(0.5, 0.08),
                   fancybox=True, shadow=True
                   )

    axes[1].legend(title="Priemerný počet API volaní",
                   handles=[red_patch1, blue_patch1],
                   bbox_to_anchor=(0.5, 0.08),
                   fancybox=True, shadow=True
                   )

    plt.tight_layout()
    savePlotsAndTables(plot=plt, functionName="webAPIonMainAndSidePages", OutputDirectory="graphs")
    plt.show()




# TODO kolko \% z celkového počtu API sa využíva.
def apiUsageAll(df: pandas.DataFrame, option):
    apis = getWebAPIs.getApis(exportDataframe=True)
    print(apis)
    # získame unique a ich počty z normal
    df_mode_0 = df[df['mode'] == 0]
    df_mode_0 = df_mode_0.groupby('func_name')['cnt'].sum().reset_index()
    df_ordered = df_mode_0.sort_values('cnt', ascending=False)
    # TODO spraviť mapu ktorá bude mapovať API_name na jednotlivé api (Background Fetch API <> Navigator.prototype.registerProtocolHandler)
    print(df_ordered)
    # získame unique a ich počty z extension
    # získame unique a ich počty z rozdielu


# TODO (koľko percent na hlavnej a vedlajších)
def mainVsSubPerc(df: pandas.DataFrame, mode: int):
    df_mode_x = df[df['mode'] == mode]
    # main a sub označiť
    pattern = re.compile(r'^https?:\/\/(www\.)?[^\/]+\.[^\/.]{2,3}(\/[a-z]{2})?\/?$')  # berie aj /en/ ako main page
    # pattern = re.compile(r'^(https?:\/\/)?(www\.)?[^\/]+\.[^\/]+\/?$')

    # Create a new column called is_main_page
    # df['is_main_page'] = df['top_level_url'].apply(lambda x: True if pattern.match(x) else False)
    df_mode_x.loc[:, 'is_main_page'] = df_mode_x['top_level_url'].apply(lambda x: True if pattern.match(x) else False)
    # print(df_mode_x.value_counts('is_main_page'))

    # celkový počet unikátnych (cnt ma nezaujima) na každej stránke
    # pre každú stránku unikátne
    tranco_func_count = df_mode_x.groupby('tranco')['func_name'].nunique()

    # unikátne na hlavnej stranke
    main_page_func_count = df_mode_x[df_mode_x['is_main_page'] == True].groupby('tranco')['func_name'].nunique()

    # unikátne na vedlajsich strankach
    subpage_func_count = df_mode_x[df_mode_x['is_main_page'] == False].groupby('tranco')['func_name'].nunique()

    # obsahuje vela Nan
    df_counts = pd.concat([tranco_func_count, main_page_func_count, subpage_func_count], axis=1,
                          keys=['whole', 'main', 'sub'])
    df_counts = df_counts.sort_values('tranco')
    # df_counts = df_counts.dropna(subset=['whole', 'main', 'sub'])

    x = df_counts.index
    plt.scatter(x, df_counts['whole'], label="Celkový počet", color='red', s=7)
    plt.scatter(x, df_counts['main'], label="Na hlavnej stránke", color='blue', s=5)
    plt.scatter(x, df_counts['sub'], label="Na podstránkach", color='orange', s=5)

    rows = int(str(df_counts.shape[0])[:2])
    rows = rows if df_counts.shape[0] > 200 else 5
    plt.xticks(df_counts.index[::rows], df_counts.index[::rows])

    # Set the x-axis label
    plt.xlabel('Tranco')

    # Set the y-axis label
    plt.ylabel('Number of unique func_name values')

    # Add a legend
    plt.legend()

    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='mainVsSubPerc', table=df_counts.to_latex())

    # Show the plot
    plt.show()


# TODO kolko percent zablokuje rozšírenie
def blockedPieChart(df, option):
    # todo pustit dalej len stránky kde tranco ma aj mode 1 a aj mode 0
    print(df.info())
    df_filtered = df.groupby('tranco').filter(lambda x: (x['mode'] == 0).any() & (x['mode'] == 1).any())
    min_t, max_t = df_filtered['tranco'].min(), df_filtered['tranco'].max()
    df_final = df_filtered.groupby('mode')['cnt'].sum().reset_index()

    data = [df_final['cnt'][0], df_final['cnt'][1]]
    without, with_ = '{:,}'.format(data[0]), '{:,}'.format(data[1])
    labels = [f'Bez rozširenia ({without})', f'S rozšírením ({with_})']
    plt.pie(data, labels=labels)
    plt.title(f"Celkový počet Webových API s rozšírením a bez neho ({min_t}-{max_t})")

    savePlotsAndTables(plot=plt, table=df_final.style.to_latex(), functionName="blockedPieChart",
                       OutputDirectory="graphs")
    plt.show()


# TODO kolko percent zablokuje rozšírenie
def numberWithAndWithoutExtension(df, option):
    # Group the data by tranco and mode
    grouped_df = df.groupby(['tranco', 'mode'])
    # Calculate the difference in the number of unique func_name values for each tranco
    difference = grouped_df['func_name'].nunique().unstack()
    # print(difference)
    difference = difference.dropna(subset=[0, 1])

    # print(difference)

    # Plot the difference in the number of unique func_name values
    plt.plot(difference.index, difference[0] - difference[1])

    # Set the tick locations and labels
    plt.xticks(difference.index[::26], difference.index[::26])

    plt.title("Kolko unikátnych API zalbokuje rozšírenie")

    # Set the x-axis label
    plt.xlabel('Tranco')

    # Set the y-axis label
    plt.ylabel('Difference in number of unique func_name values')

    savePlotsAndTables(plot=plt, table=difference.to_latex(), OutputDirectory="graphs",
                       functionName="numberWithAndWithoutExtension")

    # Show the plot
    plt.show()


# TODO rozdiel predchádzajúceho bude koľko \% z nich je použité na sledovacie účely
def privacyFocus(df, option=""):
    # Group the data by tranco and mode
    grouped_df = df.groupby(['tranco', 'mode'])
    # print(grouped_df)
    # Calculate the difference in the number of unique func_name values and cnt values for each tranco
    diff_func_name = grouped_df['func_name'].nunique().unstack().subtract(
        grouped_df['func_name'].nunique().unstack(), fill_value=0)
    diff_cnt = grouped_df['cnt'].sum().unstack().subtract(grouped_df['cnt'].sum().unstack(), fill_value=0)

    # Create a data frame with the difference values
    diff_df = pd.concat([diff_func_name, diff_cnt], axis=1)
    # print(diff_df)

    # Rename the columns
    # diff_df.columns = ['diff_func_name', 'diff_cnt']

    # Show the data frame


# vytvorí pie chart z dát ohladom tranco sites_to_be_visited, kde sa ukaze kolko stránok má kolko podstránok
def trancoExtendedGraph(stbv_path: str):
    if not os.path.isfile(stbv_path):
        print(f"ERROR: trancograpth path {stbv_path} not found ")
        return
    with open(stbv_path, 'r') as fd:
        # content = fd.read()
        jval = json.load(fd)
        print(len(jval['sites']))
    res = {}
    total = {}
    for site in jval['sites']:
        numOfLinks = len(site['links'])
        if numOfLinks == 1:
            with open('oneLinkers', 'a', encoding='utf-8') as fd:
                fd.write(f"{site['tranco_rating']}\t{site['site_url']}\n")
        if numOfLinks in res:
            res[numOfLinks] = res[numOfLinks] + 1
            total[numOfLinks] = total[numOfLinks] + numOfLinks
        else:
            res[numOfLinks] = 1
            total[numOfLinks] = numOfLinks
        # res[len(site['links'])] = len(site['links']) if len(site['links']) not in res else res[len(site['links'])] + len(site['links'])
    # res = sorted(res.items())
    print(res)
    sm = sum([v for _,v in res.items()])
    print(sm)
    labels = [f"{key} {'podstránok' if key in [5] else ('podstránka' if key in [1] else ('podstránky' if key in [2,3,4] else 'neviem'))} ({round(value/sm*100, 2)} %)" for key, value in res.items()]
    plt.pie(res.values(), labels=labels)
    # plt.title("Počet odkazov získaný z jednotlivých stránok zoznamu Tranco")

    savePlotsAndTables(plot=plt, table=str({
        'count': total,
        'number': res
    }), functionName="trancoExtendedGraph", OutputDirectory="graphs")
    plt.show()


# Removes duplicite tuples from the list of tuples
def removeDuplicates(lst: list):
    return [t for t in (set(tuple(i) for i in lst))]

def printDataframe(remaining_files_df, option="info"):
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        if option == "info":
            print(remaining_files_df.info())
        elif option == "head":
            print(remaining_files_df.head())
        elif option == "describe":
            print(remaining_files_df.describe())
        elif option == "describe2":
            print(remaining_files_df.describe(include='all'))
        elif option == "describe3":
            print(remaining_files_df.describe(include=[np.number]))
        else:
            print(remaining_files_df)


def saveDataFrame(df, filename, how, logger):
    logger.info(f"Saving dataframe as {filename}.{how}")
    if how == 'csv':
        df.to_csv(f"{filename}.csv", index=False)
    elif how == 'sqlite':
        conn = sqlite3.connect(f"{filename}.sqlite")
        df.to_sql(filename, conn, if_exists='replace', index=False)
        conn.close()
    elif how == 'json':
        df.to_json(f"{filename}.json", orient='records')
    elif how == 'pickle':
        df.to_pickle(f"{filename}.pickle")
    elif how == 'parquet':
        df.to_parquet(f"{filename}.parquet")
    elif how == 'feather':
        df.to_feather(f"{filename}.feather")
    elif how == 'hdf':
        df.to_hdf(f"{filename}.hdf", key='df', mode='w')
    elif how == 'msgpack':
        df.to_msgpack(f"{filename}.msgpack")
    elif how == 'stata':
        df.to_stata(f"{filename}.dta")
    else:
        logger.error(f"Unable to save as {how} unknown format!")
        exit()
    logger.info(f"Saved dataframe as {how}")


def merge_sqls_in_directory(filepath, logger):
    normal_db_name = sqlite3.connect("normals.sqlite")
    privacy_db_name = sqlite3.connect("privacys.sqlite")

    print(filepath)
    if os.path.isdir(filepath):
        print("Tu", filepath)
        for file in os.listdir(filepath):
            print(f"File: {file}")
            conn = sqlite3.connect(os.path.join(filepath, file))
            df = pd.read_sql("SELECT * from apis", conn)
            conn.close()
            if "agg_RESULT_" in file and "_normal" in file:
                logger.info(f"Appending {file} into normal")
                df.to_sql('apis', normal_db_name, if_exists='append', index=False)
            if "agg_RESULT_" in file and "_privacy" in file:
                logger.info(f"Appending {file} into privacy")
                df.to_sql('apis', privacy_db_name, if_exists='append', index=False)

    normal_db_name.close()
    privacy_db_name.close()

def readDataFrame(saveas_filename, saveas_filetype, logger):
    filename = f"{saveas_filename}.{saveas_filetype}"

    if not os.path.exists(filename):
        if not os.path.exists(saveas_filename):
            logger.error(f"File {filename} does not exist!")
            exit()
        else:
            filename = saveas_filename

    if saveas_filetype == "csv":
        df = pd.read_csv(filename, on_bad_lines='skip', header=None)
    elif saveas_filetype == "json":
        df = pd.read_json(filename)
    elif saveas_filetype == "pickle":
        df = pd.read_pickle(filename)
    elif saveas_filetype == "parquet":
        df = pd.read_parquet(filename)
    elif saveas_filetype == "feather":
        df = pd.read_feather(filename)
    elif saveas_filetype == "hdf":
        df = pd.read_hdf(filename)
    elif saveas_filetype == "msgpack":
        df = pd.read_msgpack(filename)
    elif saveas_filetype == "stata":
        df = pd.read_stata(filename)
    elif saveas_filetype == "sqlite":
        df = pd.read_sql(filename)
    else:
        print(f"ERROR - unknown filetype: {saveas_filetype}")
        exit()
    logger.info(f"Dataframe read {filename}!")
    return df
