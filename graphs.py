import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from helpFunctions import *


# CREATE TABLE "combined" (
# "tranco" INTEGER,
#   "func_name" TEXT,
#   "top_level_url" TEXT,
#   "url" TEXT,
#   "mode0cnt" INTEGER,
#   "mode1cnt" INTEGER,
#   "blocked" INTEGER
# )
################################################################################

@time_it
def most_used(databasename, logger):
    n = 1000
    conn = sqlite3.connect(f'{databasename}')
    # extract unique apis
    query = f"SELECT DISTINCT func_name FROM combined"
    unique_apis = pd.read_sql_query(query, conn)

    # compare with unique in apis table
    query = f"SELECT DISTINCT func_name FROM apis"
    unique_apis_apis = pd.read_sql_query(query, conn)

    # combine both tables and remove duplicates
    unique_apis = pd.concat([unique_apis, unique_apis_apis]).drop_duplicates()
    # save to file
    unique_apis.to_json('unique_apis.json', orient='records')
    logger.info(f"Saved unique apis to file: unique_apis.json")


    # 
    # most used 
    query = f"SELECT func_name, SUM(mode0cnt) as total_calls FROM combined GROUP BY func_name ORDER BY total_calls DESC LIMIT {n}"
    top_n = pd.read_sql_query(query, conn)
    savePlotsAndTables(functionName='most_used', OutputDirectory="tables", table=top_n.to_latex())
    # most blocked
    query = f"SELECT func_name, SUM(mode0cnt), SUM(mode1cnt) FROM combined GROUP BY func_name ORDER BY SUM(mode1cnt) DESC LIMIT {n}"
    top_n_blocked = pd.read_sql_query(query, conn)
    # add percentage column
    top_n_blocked['percentage'] = 1 - (top_n_blocked['SUM(mode1cnt)'] / top_n_blocked['SUM(mode0cnt)'])
    # order by percentage
    top_n_blocked = top_n_blocked.sort_values(by=['percentage'], ascending=False)
    # save to file
    top_n_blocked.to_json('top_n_blocked.json', orient='records')
    savePlotsAndTables(functionName='most_blocked', OutputDirectory="tables", table=top_n_blocked.to_latex())
    return
    query = f"SELECT func_name, SUM(mode0cnt), SUM(mode1cnt) FROM combined GROUP BY func_name ORDER BY SUM(mode1cnt) ASC LIMIT {n}"
    never_blocked = pd.read_sql_query(query, conn)
    never_blocked['percentage'] = never_blocked['SUM(mode1cnt)'] / never_blocked['SUM(mode0cnt)']
    # order by percentage
    never_blocked = never_blocked.sort_values(by=['percentage'], ascending=True) 
    savePlotsAndTables(functionName='never_blocked', OutputDirectory="tables", table=never_blocked.to_latex())
    
    # get number of sites where occur top n blocked functions
    # get blocked functions
    top_n_blocked_functions = top_n_blocked['func_name'].tolist()
    # get number of sites where occur top 100 blocked functions
    query = f"SELECT func_name, COUNT(DISTINCT url) FROM combined WHERE func_name IN {tuple(top_n_blocked_functions)} GROUP BY func_name ORDER BY COUNT(DISTINCT url) DESC"
    top_n_blocked_sites = pd.read_sql_query(query, conn)
    # add column with position where func_name is in top_n_blocked_functions
    top_n_blocked_sites['position'] = top_n_blocked_sites['func_name'].apply(lambda x: top_n_blocked_functions.index(x))


    savePlotsAndTables(functionName='top_n_blocked_sites', OutputDirectory="tables", table=top_n_blocked_sites.to_latex())
    # get number of sites where occur top n never blocked functions  
    top_n_never_blocked_functions = never_blocked['func_name'].tolist()
    query = f"SELECT func_name, COUNT(DISTINCT url) FROM combined WHERE func_name IN {tuple(top_n_never_blocked_functions)} GROUP BY func_name ORDER BY COUNT(DISTINCT url) DESC"
    top_not_blocked_sites = pd.read_sql_query(query, conn)
    top_not_blocked_sites['position'] = top_not_blocked_sites['func_name'].apply(lambda x: top_n_never_blocked_functions.index(x))
    savePlotsAndTables(functionName='top_not_blocked_sites', OutputDirectory="tables", table=top_not_blocked_sites.to_latex())
    
    # create graph with relation between top n blocked functions and top n never blocked functions
    plt.scatter(top_n_blocked_sites['position'], top_n_blocked_sites['COUNT(DISTINCT url)'], label='Top n blocked functions', marker='o')
    plt.scatter(top_not_blocked_sites['position'], top_not_blocked_sites['COUNT(DISTINCT url)'], label='Top n never blocked functions', marker='x')
    plt.legend(loc='upper right')
    plt.title('Relation between top n blocked functions and top n never blocked functions')
    plt.xlabel('Position in top n')
    plt.ylabel('Number of sites')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='relation_top_n_blocked_functions')
    plt.show()
    plt.clf()

    # create graph with relation between top n blocked functions and top n never blocked functions
    plt.scatter(top_n_blocked_sites['position'], top_n_blocked_sites['COUNT(DISTINCT url)'], label='Top n blocked functions')
    plt.scatter(top_not_blocked_sites['position'], top_not_blocked_sites['COUNT(DISTINCT url)'], label='Top n never blocked functions')
    plt.legend(loc='upper right')
    plt.title('Relation between top n blocked functions and top n never blocked functions')
    plt.xlabel('Position in top n')
    plt.ylabel('Number of sites')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='relation_top_n_blocked_functions')
    plt.show()
    plt.clf()

    # create overlay of top n blocked functions and top n never blocked functions
    plt.bar(top_n_blocked_sites['position'], top_n_blocked_sites['COUNT(DISTINCT url)'], label='Top n blocked functions')
    plt.bar(top_not_blocked_sites['position'], top_not_blocked_sites['COUNT(DISTINCT url)'], label='Top n never blocked functions')
    plt.legend(loc='upper right')
    plt.title('Relation between top n blocked functions and top n never blocked functions')
    plt.xlabel('Position in top n')
    plt.ylabel('Number of sites')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='relation_top_n_blocked_functions_overlay')
    plt.show()
    plt.clf()

    # create overlay of top n blocked functions and top n never blocked functions
    plt.bar(top_n_blocked_sites['position'], top_n_blocked_sites['COUNT(DISTINCT url)'], label='Top n blocked functions')
    plt.bar(top_not_blocked_sites['position'], top_not_blocked_sites['COUNT(DISTINCT url)'], label='Top n never blocked functions')
    plt.legend(loc='upper right')
    plt.title('Relation between top n blocked functions and top n never blocked functions')
    plt.xlabel('Position in top n')
    plt.ylabel('Number of sites')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='relation_top_n_blocked_functions_overlay')
    plt.show()
    plt.clf()
    
    

    conn.close()

################################################################################
# Plot the number of API calls per mode:
# This function will plot a bar chart showing the number of API calls
# made in each mode (normal or privacy).
# You can use this to see if there are any significant differences in API usage between the two modes.
@time_it
def plot_api_calls_per_mode(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = "SELECT mode, SUM(cnt) as total_calls FROM apis GROUP BY mode"
    data = pd.read_sql_query(query, conn)
    conn.close()
    plt.bar(data['mode'], data['total_calls'])
    plt.title('Number of API calls per mode')
    plt.xlabel('Mode')
    plt.ylabel('Number of API calls')
    plt.show()

# Plot the distribution of API calls per mode:
# This function will plot a histogram showing the distribution of API calls
# made in each mode. You can use this to see if the API usage is skewed towards
# a particular mode.
@time_it
def plot_api_calls_distribution(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = "SELECT mode, cnt FROM apis"
    data = pd.read_sql_query(query, conn)
    conn.close()
    normal_mode = data[data['mode'] == 0]['cnt']
    privacy_mode = data[data['mode'] == 1]['cnt']
    plt.hist([normal_mode, privacy_mode], bins=10, alpha=0.5, label=['Normal', 'Privacy'])
    plt.legend(loc='upper right')
    plt.title('Distribution of API calls per mode')
    plt.xlabel('Number of API calls')
    plt.ylabel('Frequency')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_api_calls_distribution')
    plt.show()


# Plot the top URLs by API calls in each mode:
# This function will plot a horizontal bar chart showing the
# top URLs by API calls in each mode.
# You can use this to see if there are any significant differences in the URLs
# that are being accessed in each mode.
@time_it
def plot_top_urls_by_api_calls(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = "SELECT mode, url, cnt FROM apis ORDER BY cnt DESC LIMIT 10"
    data = pd.read_sql_query(query, conn)
    conn.close()
    top_normal = data[data['mode'] == 0]
    top_privacy = data[data['mode'] == 1]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 6))
    ax1.barh(top_normal['url'], top_normal['cnt'], color='b')
    ax1.set_title('Top URLs by API calls (Normal)')
    ax1.set_xlabel('Number of API calls')
    ax2.barh(top_privacy['url'], top_privacy['cnt'], color='r')
    ax2.set_title('Top URLs by API calls (Privacy)')
    ax2.set_xlabel('Number of API calls')
    plt.tight_layout()
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_top_urls_by_api_calls')

    plt.show()

# Plot the API call frequency by Tranco ranking:
# This function will plot a line chart showing the frequency of API calls by
# Tranco ranking in each mode. You can use this to see if there are any significant
# differences in the API usage based on the popularity of the URLs.
@time_it
def plot_api_calls_by_tranco(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = "SELECT tranco, mode, cnt FROM apis"
    cursor = conn.execute(query)
    data = cursor.fetchall()
    conn.close()

    normal_mode = {}
    privacy_mode = {}
    for tranco, mode, cnt in data:
        if mode == 0:
            normal_mode.setdefault(tranco, 0)
            normal_mode[tranco] += cnt
        else:
            privacy_mode.setdefault(tranco, 0)
            privacy_mode[tranco] += cnt

    normal_mode_values = []
    privacy_mode_values = []
    x_ticks = []
    for i, (tranco, _) in enumerate(sorted(normal_mode.items(), key=lambda x: x[1], reverse=True)):
        normal_mode_values.append(normal_mode[tranco])
        privacy_mode_values.append(privacy_mode.get(tranco, 0))
        if i % 50 == 0:
            x_ticks.append(tranco)

    plt.plot(range(len(normal_mode_values)), normal_mode_values, color='b', label='Normal')
    plt.plot(range(len(privacy_mode_values)), privacy_mode_values, color='r', label='Privacy')
    plt.title('API calls by Tranco ranking')
    plt.xlabel('Tranco ranking')
    plt.ylabel('Number of API calls')
    plt.legend()
    plt.xticks(range(len(x_ticks)), x_ticks)
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_api_calls_by_tranco')

    plt.show()

# This function compares the number of API calls made in mode 0 and mode 1
# for each website in the dataset and returns a pandas dataframe with the results.
@time_it
def compare_modes(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    mode0_query = 'SELECT tranco, SUM(cnt) AS mode0 FROM apis WHERE mode=0 GROUP BY tranco'
    mode1_query = 'SELECT tranco, SUM(cnt) AS mode1 FROM apis WHERE mode=1 GROUP BY tranco'
    mode0 = pd.read_sql_query(mode0_query, conn)
    mode1 = pd.read_sql_query(mode1_query, conn)
    result = pd.merge(mode0, mode1, on='tranco', how='outer').fillna(0)
    result['difference'] = result['mode1'] - result['mode0']
    conn.close()
    return result

# This function plots a bar chart to compare the number of API calls made in mode 0 and mode 1
# for each website in the dataset.
@time_it
def plot_mode_comparison(databasename, logger):
    result = compare_modes(databasename=databasename, logger=logger)
    logger.info(f'Result is {result}')
    result.plot(kind='bar', y=['mode0', 'mode1'], figsize=(16, 8))
    plt.title('Comparison of API calls in mode 0 and mode 1')
    plt.xlabel('Website')
    plt.ylabel('Number of API calls')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_mode_comparison', table=result.to_latex())

    plt.show()

# This function compares the number of API calls made in mode 0 and mode 1
# for each API function and returns a pandas dataframe with the results.
@time_it
def filtering_impact(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    mode0_query = 'SELECT func_name, SUM(cnt) AS mode0 FROM apis WHERE mode=0 GROUP BY func_name'
    mode1_query = 'SELECT func_name, SUM(cnt) AS mode1 FROM apis WHERE mode=1 GROUP BY func_name'
    mode0 = pd.read_sql_query(mode0_query, conn)
    mode1 = pd.read_sql_query(mode1_query, conn)
    result = pd.merge(mode0, mode1, on='func_name', how='outer').fillna(0)
    result['difference'] = result['mode1'] - result['mode0']
    result['percent_reduction'] = result['difference'] / result['mode0'] * 100
    conn.close()
    return result

# This function plots a horizontal bar chart to compare the impact of filtering on each API function.
@time_it
def plot_filtering_impact(databasename, logger):
    result = filtering_impact(databasename=databasename, logger=logger)
    result['percent_reduction'].sort_values().plot(kind='barh', figsize=(16, 8))
    plt.title('Impact of filtering on API calls')
    plt.xlabel('Percent reduction in API calls')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_filtering_impact', table=result.to_latex())

    plt.show()

# This function groups the API calls made in mode 0 and mode 1 by top-level domain (TLD) and
# returns a pandas dataframe with the results.
# @time_it
def api_calls_by_tld(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = 'SELECT top_level_url, mode, SUM(cnt) AS total_calls FROM apis GROUP BY top_level_url, mode'
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result

# This function plots a stacked bar chart to compare the API calls made
# in mode 0 and mode 1 by TLD.
@time_it
def plot_tld_comparison(databasename, logger):
    result = api_calls_by_tld(databasename=databasename, logger=logger)
    pivot = result.pivot(index='top_level_url', columns='mode', values='total_calls')
    pivot.plot(kind='bar', stacked=True, figsize=(16, 8))
    plt.title('Comparison of API calls in mode 0 and mode 1 by TLD')
    plt.xlabel('Top-level domain')
    plt.ylabel('Number of API calls')
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_tld_comparison', table=pivot.to_latex())

    plt.show()

# This function calculates the number of blocked APIs (i.e., APIs that are in mode 0 but not in mode 1) by TLD and
# returns a pandas dataframe with the results.
# @time_it
def blocked_apis_by_tld(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = '''
        SELECT top_level_url, COUNT(*) AS num_blocked_apis
        FROM (
            SELECT func_name, top_level_url
            FROM apis
            WHERE mode = 0
            EXCEPT
            SELECT func_name, top_level_url
            FROM apis
            WHERE mode = 1
        )
        GROUP BY top_level_url
    '''
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result

# This function plots a bar chart to show the number of blocked APIs by TLD. The x-axis shows the TLDs, sorted by the
# number of blocked APIs in descending order, and the y-axis shows the number of blocked APIs on a logarithmic scale.
@time_it
def plot_blocked_apis(databasename, logger):
    result = blocked_apis_by_tld(databasename, logger)
    result = result.sort_values(by='num_blocked_apis', ascending=False)
    plt.figure(figsize=(16, 8))
    plt.bar(result['top_level_url'], result['num_blocked_apis'])
    plt.title('Number of blocked APIs by TLD')
    plt.xlabel('Top-level domain')
    plt.ylabel('Number of blocked APIs (log scale)')
    plt.yscale('log')
    plt.xticks(rotation=90)
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_blocked_apis', table=result.to_latex())

    plt.show()

# This function plots a scatter plot to show the relationship between the position in the Tranco list and the number
# and type of blocked APIs. The x-axis shows the position in the Tranco list (on a logarithmic scale), and the y-axis
# shows the number of blocked APIs (on a logarithmic scale). The color of each point indicates the TLD.
@time_it
def plot_position_vs_blocked_apis(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = '''
        SELECT tranco, top_level_url, COUNT(*) AS num_blocked_apis
        FROM (
            SELECT tranco, func_name, top_level_url
            FROM apis
            WHERE mode = 0
            EXCEPT
            SELECT tranco, func_name, top_level_url
            FROM apis
            WHERE mode = 1
        )
        GROUP BY tranco, top_level_url
    '''
    result = pd.read_sql_query(query, conn)
    conn.close()

    tlds = result['top_level_url'].unique()
    tld_colors = {}
    for i, tld in enumerate(tlds):
        tld_colors[tld] = plt.get_cmap('Dark2')(i)

    plt.figure(figsize=(16, 8))
    for tld in tlds:
        data = result[result['top_level_url'] == tld]
        plt.scatter(data['tranco'], data['num_blocked_apis'], c=tld_colors[tld], alpha=0.7, label=tld, s=10)
    plt.title('Position in Tranco vs. number of blocked APIs')
    plt.xlabel('Position in Tranco (log scale)')
    plt.ylabel('Number of blocked APIs (log scale)')
    plt.xscale('log')
    plt.yscale('log')
    plt.legend()
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_position_vs_blocked_apis')

    plt.show()

# This function will extract the most frequent API calls from the database and return a pandas dataframe with the results.
@time_it
def df_most_frequent_apis(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    query = '''
        SELECT func_name, top_level_url, mode, SUM(cnt) AS total_calls
        FROM apis
        GROUP BY func_name, top_level_url, mode
        ORDER BY total_calls DESC
    '''
    result = pd.read_sql_query(query, conn)
    savePlotsAndTables(OutputDirectory='graphs', functionName='df_most_frequent_apis', table=result.to_latex())
    conn.close()
    return result

# This function will extract the most frequently blocked API calls from the database and return a pandas dataframe with the results. 
@time_it
def df_most_frequent_blocked_apis(databasename, logger):
    # Connect to the database
    conn = sqlite3.connect(databasename)

    # Retrieve the data for mode 0 and mode 1
    df = pd.read_sql_query("SELECT func_name, mode, tranco, url, SUM(cnt) as cnt FROM apis GROUP BY func_name, mode, tranco, url", conn)

    # Filter to only include mode 0 and mode 1
    df = df[df['mode'].isin([0, 1])]

    # Create a pivot table to get the counts of each API by mode and URL
    pivot = pd.pivot_table(df, index=['func_name', 'url'], columns='mode', values='cnt', aggfunc='sum', fill_value=0)

    # Calculate the difference between mode 0 and mode 1 in percentage
    pivot['diff_percent'] = ((pivot[1] - pivot[0]) / pivot[0]) * 100

    # Get the top 1000 URLs with the most APIs in total
    top_urls = df.groupby('url')['cnt'].sum().nlargest(1000).index.tolist()

    # Filter to only include the top 1000 URLs
    pivot = pivot[pivot.index.get_level_values('url').isin(top_urls)]

    # Reset the index and rename the columns
    pivot = pivot.reset_index().rename(columns={0: 'mode_0', 1: 'mode_1'})

    # Sort by the difference between mode 0 and mode 1 in descending order
    pivot = pivot.sort_values('diff_percent', ascending=False)

    # Display the result
    print(pivot.head())
    savePlotsAndTables(OutputDirectory='graphs', functionName='df_most_frequent_blocked_apis', table=pivot.to_latex())
    conn.close()
    return pivot

# This function will extract functions that were always blocked and the ones that were never blocked
@time_it
def df_always_never_blocked_apis(databasename, logger):
    conn = sqlite3.connect(f'{databasename}')
    always_filtered = pd.read_sql_query("SELECT func_name FROM apis WHERE mode=1 AND func_name NOT IN (SELECT func_name FROM apis WHERE mode=0)", conn)

    never_filtered = pd.read_sql_query("SELECT func_name FROM apis WHERE mode=0 AND func_name NOT IN (SELECT func_name FROM apis WHERE mode=1)", conn)

    savePlotsAndTables(OutputDirectory='graphs', functionName='df_always_never_blocked_apis', table=always_filtered.to_latex())
    savePlotsAndTables(OutputDirectory='graphs', functionName='df_always_never_blocked_apis', table=never_filtered.to_latex())
    conn.close()

    return (always_filtered, never_filtered)

# this function will show relationship between the number of APIs on a site and the number of filtered APIs on the same site using a scatter plot.
@time_it
def plot_filtered_vs_total_apis(database_name, logger):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    # Retrieve data from the database
    c.execute("""
        SELECT tranco, mode, SUM(cnt)
        FROM apis
        GROUP BY tranco, mode
    """)
    data = c.fetchall()

    # Transform the data into a dictionary of {tranco: [total_apis, filtered_apis]}
    tranco_data = {}
    for tranco, mode, cnt in data:
        if tranco not in tranco_data:
            tranco_data[tranco] = [0, 0]
        tranco_data[tranco][mode] = cnt

    # Create a list of tuples (total_apis, filtered_apis) for each tranco
    api_data = [(total_apis, filtered_apis) for total_apis, filtered_apis in tranco_data.values()]

    # Plot the data as a scatter plot
    plt.scatter([d[0] for d in api_data], [d[1] for d in api_data], s=10)
    plt.xlabel('Total Apis')
    plt.ylabel('Filtered Apis')
    plt.title('Filtered vs Total Apis')
    plt.show()
    savePlotsAndTables(plot=plt, OutputDirectory='graphs', functionName='plot_filtered_vs_total_apis')
    conn.close()
    return api_data


#########################################################################