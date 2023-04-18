#!/usr/bin/python3

import argparse
import logging
import os
import shutil
import graphs as gp

import matplotlib.pyplot as plt
import json
from helpFunctions import *
from shutil import rmtree
from getWebAPIs import *
import pandas as pd
from helpFunctions import saveDataFrame, readDataFrame


# Makes dictionary of filetypes and paths
def makeDictOfResources(path: str, logger) -> dict:
    try:
        if not os.path.isdir(path):
            raise FileNotFoundError

        all_paths = os.listdir(path=path)
        response = {
            "priv_Dirs": [], "normDirs": [],
            "priv_Zips": [], "normZips": [],
            "unknown": []}

        for path_ in all_paths:
            path_ = f"{path}{path_}"
            if os.path.isdir(path_):
                if getFolderSize(path_) < 50:
                    logger.info(f"Directory {path_} is almost empty -> removing ...")
                    rmtree(path_, ignore_errors=True)
                    continue
                if "priv" in path_:
                    response["priv_Dirs"].append(path_)
                else:
                    response["normDirs"].append(path_)
            elif os.path.isfile(path_) and isZip(path_):
                if "priv" in path_:
                    response["priv_Zips"].append(path_)
                else:
                    response["normZips"].append(path_)
            else:
                response["unknown"].append(path_)
        return response

    except FileNotFoundError:
        logger.error(f"File {path} is not directory!")


def createCommandsFromLog(resultFrom: list) -> list:
    result, r_values = [], []
    resutdicts = []
    for i in resultFrom:
        for dictionary in i:
            columns = ', '.join([k for k, v in dictionary.items()][:-1])
            values = ', '.join(['?' for i in range(len(dictionary) - 1)])
            r_values.append([v for k, v in dictionary.items()][:-1])
            result.append(f"INSERT INTO {dictionary['tablename']}({columns}) VALUES ({values})")
            resutdicts.append(dictionary)
    return result, r_values, resutdicts


def writeInterval(interval: str, resourceType: str, size: int):
    data = {"interval": interval, "resourceType": resourceType, "size": size}
    with open("intervals.json", 'a') as fd:
        fd.write(f"{data}")
        # TODO check


def parseZips(paths: list, resourcetype: str, directory_: str, logger):
    retval = []
    for _zipFile in paths:
        zipfilenoext = _zipFile.split('/')[-1].rstrip(".zip")
        # rozbalit do priecinka
        with zipfile.ZipFile(_zipFile, 'r') as zip_fd:
            zip_fd.extractall(zipfilenoext)

        # skontrolovat strukturu sqlite a log
        sqliteDB = findOneByExtension(zipfilenoext, "sqlite", logger)  # ak nenájde bude None
        logfile = findOneByExtension(zipfilenoext, "log", logger)

        # spracovat log a sqlite
        if logfile != None:
            flag = determineFlagFromLogFile(logfile)
            if flag != "U":
                resourcetype = "_privacy" if flag == "P" else "_normal"

            _list_to_parse = getFromContent(readFile(logfile))

            # extrahovat useful info
            try:
                df_joined, df_sites = getPandas(sqliteDB)
                if _list_to_parse != [[], []]:
                    # logger.warning(f"LIST to parse neni empty: {sqliteDB}")
                    logger.info(f"List to parse at {sqliteDB}")
                    sqlitecommands, sqlitevalues, dicts = createCommandsFromLog(_list_to_parse)
                    df_logs = pd.DataFrame.from_records(dicts)
                    df_only_important = df_logs[
                        ['document_url', 'func_name', 'top_level_url', 'browser_id', 'visit_id']]

                    df_joined = pd.concat([df_joined, df_only_important], join="outer")

                df_all, interval = mergeDF(df_joined, df_sites)
                filename = f"RESULT_{interval}{resourcetype}"
                retval.append(filename)
                logger.info(f"writing - {filename} into {directory_}")
                writeDB(df_all, name=filename, directory=directory_)

            except Exception as ex:
                logger.warning(f"Unable to load DB from {sqliteDB}, reason: {ex}")

        # vymazat extrahovany priecinok
        rmtree(zipfilenoext, ignore_errors=True)
        return retval


def parseDirectiories(paths: list, resourcetype: str, directory_: str, logger):
    for directory in paths:
        # skontrolovat štruktúru _data/ [screenshots, sources - optional] crawl-data.sqlite, openwpm.log - required
        _data_path = f"{directory}/_data"
        logger.info(f"Doing: {directory}")
        if os.path.isdir(_data_path):
            sqliteDB = findOneByExtension(_data_path, "sqlite", logger)  # ak nenájde bude None
            logfile = findOneByExtension(_data_path, "log", logger)
            # ak je log vytvoriť json ktory bude v sebe obsahovat potrebné udaje z logu
            if logfile != None:
                flag = determineFlagFromLogFile(logfile)
                if flag != "U":
                    resourcetype = "_privacy" if flag == "P" else "_normal"
                logger.info(f"flag: {flag}")
                _content = readFile(logfile)
                logger.info(f"content {len(_content)}")
                _list_to_parse = getFromContent(_content)
                logger.info(f"list to parse {_list_to_parse}")
                if _list_to_parse != [[], []]:
                    print("-------------------------------------------")
                    logger.info(f"ROOOOOOOOOO log file {logfile, len(_list_to_parse[0]), len(_list_to_parse[1])}")
                    print("-------------------------------------------")

            # extrahovat useful info
            try:
                logger.info(f"db: {sqliteDB}")
                df_joined, df_sites = getPandas(sqliteDB)
                logger.info(f"df_joined {df_joined}")
                df_all, interval = mergeDF(df_joined, df_sites)
                logger.info(f"interval {interval}")
                # writeInterval(interval, resourcetype, df_all.size())
                logger.info(f"Writing db")
                writeDB(df_all, name=f"RESULT_{interval}{resourcetype}", directory=directory_)
            except Exception as ex:
                logger.warning(f"Unable to load DB from {sqliteDB}, reason: {ex}")
        else:
            logger.debug(f"parseDirectiories: {directory} does not have /_data subpath")


def main_parse(filepath: str, logger):
    filepaths = makeDictOfResources(filepath, logger=logger)
    logger.info(f"Parsing normal directories: {filepaths['normDirs']}")
    parseDirectiories(filepaths["normDirs"], "norm", "result", logger)

    logger.info(f"Parsing privacy directories: {filepaths['priv_Dirs']}")
    parseDirectiories(filepaths["priv_Dirs"], "priv", "result", logger)

    logger.info(f"Parsing privacy zips directories: {filepaths['priv_Zips']}")
    parseZips(filepaths["priv_Zips"], "priv", "result", logger)

    logger.info(f"Parsing normal zips directories: {filepaths['normZips']}")
    parseZips(filepaths["normZips"], "norm", "result", logger)

@time_it
def main_graphs(filepath: str, logger):
    if not os.path.isfile(filepath):
        logger.error(f"ERROR - unknown file, put the path with filename of aggregated and merged crawled data")
        exit()
    if not checkExtension(filepath, ".sqlite"):
        logger.error(f"ERROR - put the path with filename of aggregated and merged crawled data and sqlite extension (GOT: {filepath})")
        exit()
    main_graphs_sqlite(filepath, logger)
    return 0
    conn = sqlite3.connect(filepath)
    df_orig = pd.read_sql("SELECT * FROM apis", con=conn)
    df_orig = df_orig.astype({'tranco': int})
    # check size of df_orig
    logger.info(f"df_orig size: {df_orig.size}")
    ############## GRAPHS ##############
    mostUsedAPIs(df_orig, True)
    mostUsedAPIs(df_orig, False)

    impactOfExtensionOnAPIsThroughTranco(df_orig, "")

    webAPIonMainAndSidePages(df=df_orig)

    # # # TODO
    apiUsageAll(df_orig, "")
    #
    mainVsSubPerc(df=df_orig, mode=0)
    mainVsSubPerc(df=df_orig, mode=1)
    #
    numberWithAndWithoutExtension(df=df_orig, option="")
    #
    blockedPieChart(df=df_orig, option="")
    #
    privacyFocus(df_orig)
    #
    trancoExtendedGraph("tranco/sites_to_be_visited.json")

    # TODO kolko % api sa zablokovalo na danej stránke
    #     tabuľka na 1265 stánkach bolo zablokovaných 1235091 API čo predstavovalo 10-15% webových API

    ####################################
    conn.close()


def main_aggregate(filepath: str = "", logger=None, dbPath: str = None):
    tablename = "apis"
    allsqlites = "all"
    aggregatedDirecotry = "aggregated"
    if not os.path.isdir(aggregatedDirecotry) and dbPath in None:
        os.mkdir(aggregatedDirecotry)
    if not os.path.isdir(filepath) and not filepath == "" :
        logger.error(f"Specified path:{filepath} is not valid directory!")
        exit()
    elif filepath == "" and dbPath is not None:
        # logger.info(f"Aggregating {dbPath}")
        if os.path.isfile(dbPath):
            if not os.path.isdir("crawl_aggregated"):
                os.mkdir("crawl_aggregated")
            # logger.info(f"\tPATH OK {dbPath}")
            conn = sqlite3.connect(dbPath)
            # logger.info(f"\tCONNECTED OK {dbPath}")
            df_aggregated = pd.read_sql(f"""SELECT func_name, tranco, top_level_url, url, COUNT(*) AS cnt
                            FROM {tablename}
                            GROUP BY func_name, tranco, top_level_url, url""", con=conn)
            logger.info(f"\tEXTRACTED OK {dbPath}")
            conn2 = sqlite3.connect(f"crawl_aggregated/agg_{dbPath.split('/')[1].split('.')[0]}.sqlite")
            # logger.info(f"\tCREATED OK {dbPath}")
            df_aggregated.to_sql('apis', conn2, if_exists='replace', index=False)
            logger.info(f"\tDUMPED OK {dbPath}")
            conn2.close()
            conn.close()
            return True
        else:
            logger.error(f"Specified path:{dbPath} is not valid file!")
            return False

    for sqlite in os.listdir(filepath):
        sqlite_agg = f"{aggregatedDirecotry}/{sqlite}"
        sqlite = f"{filepath}/{sqlite}"
        print(sqlite)
        conn = sqlite3.connect(sqlite)
        # aggregateData(conn, sqlite)
        df_aggregated = pd.read_sql(f"""SELECT func_name, tranco, top_level_url, url, COUNT(*) AS cnt
                        FROM {tablename}
                        GROUP BY func_name, tranco, top_level_url, url""", con=conn)
        conn2 = sqlite3.connect(sqlite_agg)
        df_aggregated.to_sql('apis', conn2, if_exists='replace', index=False)
        conn2.close()
        conn.close()


def main_merge(filepath: str, logger):
    # FIXME po mergovaní zmazat agregované
    checkDirectory(filepath)
    fconn = sqlite3.connect(f"{filepath}/aggregated.sqlite")
    if filepath.endswith("extracted"):
        filepath = filepath + "/crawl_aggregated"
    for directory in os.listdir(filepath):
        fullpath = f"{filepath}/{directory}"
        if checkExtension(directory, ".sqlite"):
            try:
                if "aggregated.sqlite" in fullpath:
                    continue

                conn = sqlite3.connect(fullpath)
                df = pd.read_sql_query("SELECT * FROM apis", conn)
                if "_normal" in directory:
                    logger.info("normal assigning 0")
                    df = df.assign(mode=0)
                elif "_privacy" in directory:
                    logger.info("privacy assigning 1")
                    df = df.assign(mode=1)
                else:
                    logger.info("unknown assigning -1")
                    df = df.assign(mode=-1)
                logger.info(f"merging {fullpath}")
                # add tranco column as int
                df = df.astype({'tranco': int})
                df.to_sql("apis", con=fconn, if_exists='append')
                conn.close()
            except sqlite3.OperationalError as err:
                print(f"Error - {err}")
    fconn.close()


def extract_info_from_filepath(filepath: str):
    file_name = os.path.basename(filepath)
    match = re.match("crawl_([0-9]+)-([0-9]+)(?:_(privacy))?(?:(\.zip))?", file_name)
    if match:
        od = match.group(1)
        do = match.group(2)
        mode = match.group(3) if match.group(3) and match.lastindex >= 3 else "normal"
        file_type = match.group(4) if match.group(4) and match.lastindex >= 4 else "directory"
        flag = True
    else:
        flag = False
        od = None
        do = None
        mode = None
        file_type = None
    return od, do, mode, file_type, flag


def createDataframe(remaining_files, logger):
    remaining_files_df = pd.DataFrame(remaining_files, columns=["file_path"])
    remaining_files_df[['od', 'do', 'mod', 'file_type', 'flag']] = remaining_files_df['file_path'].apply(
        extract_info_from_filepath).apply(pd.Series)
    remaining_files_df = remaining_files_df.astype({'od': int, 'do': int})
    remaining_files_df = remaining_files_df.sort_values(by=['od', 'do'])
    return remaining_files_df


def saveAndMergeDataframes(df_old: pd.DataFrame, df_new: pd.DataFrame, saveas_filename: str, saveas_filetype: str,
                           logger: logging.Logger):
    try:
        df = pd.concat([df_old, df_new], ignore_index=True, sort=True).drop_duplicates()
        df = df.sort_values(by=['od', 'do'])
    except Exception as ex:
        logger.error(f"Error - {ex}")
        exit()
    saveDataFrame(df, saveas_filename, saveas_filetype, logger)


def main_save(folderpath: str, logger: logging.Logger, saveas_filename: str, saveas_filetype: str):
    crawl_pattern = "crawl_[0-9]+-[0-9]+(?:_privacy)?"  # crawl_1-100 or crawl_1-100_privacy
    remaining_files = []

    if not os.path.exists(folderpath):
        logger.error(f"Specified path:{folderpath} is not valid directory!")
        exit()
    for root, dirs, files in os.walk(folderpath):
        # print(root, dirs, files)
        for file in files:
            if re.match(crawl_pattern, file):
                remaining_files.append(os.path.join(root, file))
        for dir in dirs:
            if re.match(crawl_pattern, dir):
                remaining_files.append(os.path.join(root, dir))
        break
    df = createDataframe(remaining_files, logger)
    if os.path.exists(f"{saveas_filename}.{saveas_filetype}"):
        logger.info(f"File {saveas_filename}.{saveas_filetype} already exists, merging with new data!")
        df_old = readDataFrame(saveas_filename, saveas_filetype, logger)
        saveAndMergeDataframes(df_old, df, saveas_filename, saveas_filetype, logger)
        logger.info(f"Dataframe merged!")
    else:
        logger.info(f"File {saveas_filename}.{saveas_filetype} does not exist, creating new one!")
        saveDataFrame(df, saveas_filename, saveas_filetype, logger)
        logger.info(f"Dataframe created!")


def rangeOfUndoneFromDataframe(df: pd.DataFrame, logger: logging.Logger, mode: str) -> list:
    df_normal = df.loc[df['mod'] == mode]

    subset = df_normal[['od', 'do']].drop_duplicates().sort_values(by=['od', 'do'])
    tuples = [tuple(x) for x in subset.to_numpy()]
    undone = []
    lokal_min = 1
    for (od, do) in tuples:
        if od == lokal_min:
            lokal_min = do
            continue
        elif od > lokal_min:
            undone.append((lokal_min, od))
            lokal_min = do
        else:
            print(f"ERROR - {od} < {lokal_min}")

    return undone


def createUndoneDataframe(df, logger):
    # get undone tuples
    undone_normal = rangeOfUndoneFromDataframe(df, logger, "normal")
    undone_privacy = rangeOfUndoneFromDataframe(df, logger, "privacy")

    df_normal = pd.DataFrame(undone_normal, columns=['od', 'do'])
    df_privacy = pd.DataFrame(undone_privacy, columns=['od', 'do'])
    df_normal["mod"] = "normal"
    df_privacy["mod"] = "privacy"
    df_concat = pd.concat([df_normal, df_privacy], ignore_index=True, sort=True).drop_duplicates()
    df_concat['file_path'] = None
    df_concat['file_type'] = None
    df_concat['flag'] = False
    return df_concat


# flag can be true (privacy), false (no privacy), None (Both)
def main_generate_range(fromto: str, step, filepath, flag):
    fromto = fromto.split("-")
    fromto = [int(x) for x in fromto]
    fromto.sort()
    _from = fromto[0]
    _to = fromto[1]
    i = _from
    ranges = []
    while (i + step <= _to):
        ranges.append(f"{i}-{i + step}")
        i = i + step
    if (i < _to):
        ranges.append(f"{i}-{_to}")

    with open(filepath, "w") as f:
        for r in ranges:
            if flag is not None:
                f.write(f"{r}{'-privacy' if flag else ''}\n")
            else:
                f.write(f"{r}\n")
                f.write(f"{r}-privacy\n")


def main_graph_tranco(filepath: str, logger: logging.Logger):
    if not os.path.isfile(filepath):
        logger.error(f"Specified path:{filepath} is not valid file!")
    # read csv with names tranco,url,is_ok,is_redirect,status_code,captcha,encoding
    df = pd.read_csv(filepath, names=["tranco", "url", "is_ok", "is_redirect", "status_code", "captcha", "encoding"],
                     on_bad_lines='skip')
    # order by tranco
    df = df.sort_values(by=['tranco'])
    # get first 250 000
    df = df.head(250000)
    # captcha
    ax = sns.countplot(x='captcha', data=df)
    ax.bar_label(ax.containers[0])
    plt.show()

    # create graph with counts of unique status_code
    ax = sns.countplot(x='status_code', data=df, order=df.status_code.value_counts().iloc[:10].index)
    ax.bar_label(ax.containers[0])
    plt.show()

    # get number of sites where status_code is 200 and captcha is True
    df_200 = df.loc[df['status_code'] == 200]
    df_200_captcha = df_200.loc[df_200['captcha'] == True]
    logger.info(f"Number of sites where status_code is 200 and captcha is True: {len(df_200_captcha)}")

    df_200_captcha = df_200.loc[df_200['captcha'] == False]
    logger.info(f"Number of sites where status_code is 200 and captcha is False: {len(df_200_captcha)}")

    # get sites where status_code is -1
    df_err = df.loc[df['status_code'] == -1]
    # get encoding column
    df_err = df_err['encoding']

    errors = {
        "2XX": len(df.loc[(df['status_code'] >= 200) & (df['status_code'] <= 299)]),
        "3XX": len(df.loc[(df['status_code'] >= 300) & (df['status_code'] <= 399)]),
        "4XX": len(df.loc[(df['status_code'] >= 400) & (df['status_code'] <= 499)]),
        "5XX": len(df.loc[(df['status_code'] >= 500) & (df['status_code'] <= 599)]),
        "captcha": len(df.loc[df['captcha'] == True]),
        "above 300": len(df.loc[df['status_code'] > 299]),
        "unsafe_legacy": len(df_err.loc[df_err.str.contains('UNSAFE_LEGACY_RENEGOTIATION_DISABLED')]),
        "hostname_mismatch": len(df_err.loc[df_err.str.contains('No address associated with hostname')]),
        "ssl_error": len(df_err.loc[df_err.str.contains("CertificateError")]),
        "-1": len(df.loc[df['status_code'] == -1]),
        "timeout": len(df_err.loc[df_err.str.contains('Read timed out.')]),
        "remotedisconect": len(df_err.loc[df_err.str.contains('RemoteDisconnected')]),
        "unreachable": len(df_err.loc[df_err.str.contains('Network is unreachable')])
    }
    # get number of sites where status_code is above 300
    print(f"Number of sites where status_code is above 300: {errors['above 300']}")

    # get number of rows where UNSAFE_LEGACY_RENEGOTIATION_DISABLED is in encoding
    print(f"Number of sites where UNSAFE_LEGACY_RENEGOTIATION_DISABLED is in encoding: {errors['unsafe_legacy']}")
    # get number of rows containing 'No address associated with hostname'
    print(f"Number of sites where No address associated with hostname is in encoding: {errors['hostname_mismatch']}")

    # get number of rows containing 'SSLError(CertificateError'
    print(f"Number of sites where SSLError(CertificateError is in encoding: {errors['ssl_error']}")

    df_err.to_csv("encoding_err.csv", index=False, header=False)
    print(f"Number of sites where status_code is -1: {errors['-1']}")

    # get number of rows containing  Read timed out.
    print(f"Number of sites where Read timed out. is in encoding: {errors['timeout']}")

    # get number of rows containing RemoteDisconnected
    print(f"Number of sites where RemoteDisconnected is in encoding: {errors['remotedisconect']}")

    # get number of rows containing Network is unreachable
    print(f"Number of sites where Network is unreachable is in encoding: {errors['unreachable']}")

    # get number of rows with url containing dns
    df_dns = df[df['url'].str.contains("dns")]
    print(f"Number of rows with url containing dns: {len(df_dns)}")

    # get number of rows with url containing server
    df_server = df[df['url'].str.contains("server")]
    print(f"Number of rows with url containing server: {len(df_server)}")

    # create pie chart with data from errors and df_dns, df_server
    labels = ['2XX', '3XX', '4XX', '5XX', 'captcha', 'unsafe_legacy', 'hostname_mismatch', 'ssl_error', 'timeout',
              'remotedisconect', 'unreachable', 'dns', 'server']
    sizes = [errors['2XX'], errors['3XX'], errors['4XX'], errors['5XX'], errors['captcha'], errors['unsafe_legacy'],
             errors['hostname_mismatch'], errors['ssl_error'], errors['timeout'], errors['remotedisconect'],
             errors['unreachable'], len(df_dns), len(df_server)]

    # create table with labels and sizes with percentage
    table = pd.DataFrame({'labels': labels, 'sizes': sizes})
    table['percentage'] = table['sizes'] / table['sizes'].sum() * 100
    table['percentage'] = table['percentage'].round(2)
    table = table.sort_values(by=['sizes'], ascending=False)
    print(table)
    # save table as latex
    table.to_latex("table.tex", index=False)

    plt.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    # plt.legend(labels, loc="best")
    plt.show()

    # get duplicities of tranco column
    # df = df.groupby('tranco').size().reset_index(name='counts').sort_values(by=['counts'], ascending=False)
    # # create pie chart
    # ax = sns.countplot(x="counts", data=df)
    # ax.set_title("Number of websites with same number of tranco")
    # ax.bar_label(ax.containers[0])
    # plt.show()
    # print(df)

    # crate graph with counts of unique encoding
    # df_encoding = df.groupby('encoding').size().reset_index(name='counts')
    # # sort by counts and extract top 10
    # df_encoding = df_encoding.sort_values(by=['counts'], ascending=False).head(10)
    # df_encoding.plot.bar(x='encoding', y='counts', rot=0)
    # plt.show()
    # # crate graph with counts of unique captcha
    # df_captcha = df.groupby('captcha').size().reset_index(name='counts')


def main_generateAPIs(filepath: str, logger: logging.Logger, strict=False, output: str = "OUTPUT"):
    logger.info("Generating APIs")
    logger.info(f"Creating {filepath}")
    if strict:
        # remove (UPDATE) existing filepaht with all contents
        if os.path.isdir(filepath):
            shutil.rmtree(filepath)

    # if not os.path.isfile("backup.df"):
    df_basic = getApis(exportDataframe=True)
        # save dataframe into file
        # df_basic.to_pickle("backup.df")
    print(f"dataframe info {df_basic.info()}")
    # check if file with dataframe exists
    # if os.path.isfile("backup.df"):
        # load dataframe from file
        # df_basic = pd.read_pickle("backup.df")
    if filepath is not None:
        if not os.path.isdir(filepath):
            os.mkdir(filepath)
        crawlAPIS(dataframe=df_basic, logger=logger, filepath=f"{output}/{filepath}")

    print("DONE")

def main_graphs_sqlite(filepath: str, logger: logging.Logger):
    logger.info("Generating graphs")
    gp.most_used(databasename=filepath, logger=logger)
    logger.info("Generating plot_api_calls_distribution")
    # gp.plot_api_calls_distribution(databasename=filepath, logger=logger)
    # logger.info("Generating plot_api_calls_per_mode")
    # gp.plot_api_calls_per_mode(databasename=filepath, logger=logger)
    # logger.info("Generating plot_top_urls_by_api_calls")
    # gp.plot_top_urls_by_api_calls(databasename=filepath, logger=logger)
    # logger.info("Generating plot_api_calls_by_tranco")
    # gp.plot_api_calls_by_tranco(databasename=filepath, logger=logger)

    # logger.info("Generating plot_mode_comparison")
    # gp.plot_mode_comparison(databasename=filepath, logger=logger)

    # logger.info("Generating plot_filtering_impact")
    # gp.plot_filtering_impact(databasename=filepath, logger=logger)
    # logger.info("Generating plot_tld_comparison")
    # gp.plot_tld_comparison(databasename=filepath, logger=logger)
    # logger.info("Generating plot_blocked_apis")
    # gp.plot_blocked_apis(databasename=filepath, logger=logger)
    # logger.info("Generating plot_position_vs_blocked_apis")
    # gp.plot_position_vs_blocked_apis(databasename=filepath, logger=logger)

    # logger.info("Generating df_most_frequent_apis")
    # gp.df_most_frequent_apis(databasename=filepath, logger=logger)

    # logger.info("Generating df_most_frequent_blocked_apis")
    # gp.df_most_frequent_blocked_apis(databasename=filepath, logger=logger)

    # logger.info("Generating df_always_never_blocked_apis")
    # gp.df_always_never_blocked_apis(databasename=filepath, logger=logger)

    # logger.info("Generating plot_filtered_vs_total_apis")
    # gp.plot_filtered_vs_total_apis(databasename=filepath, logger=logger)


def main_parseRanges(filepath: str, logger: logging.Logger):
    savedir = f"{filepath}/extracted"
    # get all zip files in filepath directory
    if not os.path.isdir(filepath):
        logger.warning(f"main_parseRanges - Unable to find directory {filepath}")
    zips = []
    for file in os.listdir(filepath):
        if file.endswith(".zip"):
            zips.append(file)

    if zips != []:
        if not os.path.isdir(savedir):
            logger.info(f"Creating {savedir} directory for extracting")
            os.mkdir(savedir)

    # extract zips into folder "extracted"
    # for zip in zips:
    #     logger.info(f"Extracting {zip} into {savedir}")
    #     with zipfile.ZipFile(f"{filepath}/{zip}", 'r') as zip_fd:
    #         zip_fd.extractall(f"{savedir}")
    # input("continue to merge?")
    # merge files in extracted into one big sqlite db

    # for file_sqlite in os.listdir(savedir):
    #     print(file_sqlite)
    #     directory = f"{savedir}/{file_sqlite}"
    #     if os.path.isdir(directory):
    #         print("here")
    #         merge_sqls_in_directory(directory, logger=logger)

    # main_merge(savedir, logger) # merge all files in extracted into one big sqlite aggregated.sqlite

    # aggregated.sqlite should be generated in savedit
    # analyze the DB
    logger.info(f"Normalizing {filepath}/aggregated.sqlite")

    # add columns
    # trancos = get_n_entries_based_on_column_name(f"{filepath}/aggregated.sqlite", 'apis', 1000, 'tranco')
    # # will create reduced.sqlite with only 1000 trancos
    # dbentries = extract_data_from_database_where_column_has_values(database, 'apis', 'tranco', [i[0] for i in trancos])
    # add_columns_to_table(database, 'apis') 

    # main_graphs(filepath=f"{savedir}/aggregated.sqlite", logger=logger)
    main_graphs_sqlite(filepath=f"{savedir}/aggregated.sqlite", logger=logger)

if __name__ == "__main__":
    # Parsing arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", help="Path to the folder with crawled data. (1) (as dir/)", required=False)
    parser.add_argument("-a", "--aggregate", help="Program will aggregate files in specified folder. (2)",
                        required=False)
    parser.add_argument("-m", "--merge", help="Program will merge files in specified folder into one. (3)",
                        required=False)
    parser.add_argument("-g", "--graphs", help="Program will analyze data from aggregated and merged file.",
                        required=False)
    parser.add_argument("-s", "--save", help="Program will create or update existing json with crawled data.", required=False)
    parser.add_argument("-aa", "--all", help="Program will do --path, --aggregate, --merge", required=False)
    parser.add_argument("-gt", "--graphtranco", help="Program will parse data about crawled sites", required=False)
    parser.add_argument("--generate_range", help="Program will generate range of numbers in range from-to", required=False)
    parser.add_argument("--step", help="Program will generate range of numbers in range from-to specified by step", required=False, default=100, type=int)
    parser.add_argument("-ga", "--generateAPIs", help="Program will generate updated json files containing Web API infrmation", required=False)
    parser.add_argument("-pr", "--parseRanges", help="Program will analyze data in .zip formats", required=False)
    parser.add_argument("-o", "--output", help="Output direcotry", required=False)
    args = parser.parse_args()

    # Setting up logger
    logger = setLogger("../logs.txt")

    if args.output:
        if not os.path.isdir(args.output):
            os.mkdir(args.output)

    # Call main 
    if args.save:
        main_save(folderpath=args.save, logger=logger, saveas_filename="crawled", saveas_filetype="csv")
    elif args.generate_range:
        main_generate_range(args.generate_range, args.step, "ranges.txt", None)
    elif args.generateAPIs:
        main_generateAPIs(filepath=args.generateAPIs, logger=logger, output=args.output)
    elif args.parseRanges:
        main_parseRanges(filepath=args.parseRanges, logger=logger)
    elif args.all:
        logger.info("Starting all")
    elif args.graphtranco:
        main_graph_tranco(filepath=args.graphtranco, logger=logger)
    elif args.path:
        # extrahuje zo súborov a zipov potredbne udaje do jedného sqlite
        main_parse(filepath=args.path, logger=logger)
    elif args.merge:
        # spoji všetky v priecinku do jedného
        main_merge(filepath=args.merge, logger=logger)
    elif args.aggregate:
        # spoji rovnake riadky do jedneho
        main_aggregate(filepath=args.aggregate, logger=logger)
    elif args.graphs:
        # spoji rovnake riadky do jedneho
        main_graphs(filepath=args.graphs, logger=logger)
    else:
        main_graphs(filepath="/aggregated/aggregated.sqlite", logger=logger)
        print("Unknown input")
    logger.info("Finished")
