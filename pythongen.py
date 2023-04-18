import os, sys, re, json
import argparse
from urllib.parse import urlparse
from templates import *

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

def implemented_apis(path):
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
    return apis

def all_apis(path):
    if not os.path.exists(path):
        print("The specified path does not exist.")
        exit(1)
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

    print(domains)
    with open("sources.json", "w") as f:
        json.dump(sources, f, indent=4)
    return apis

def fillSettings(wholeAPI, treshold):
    totalLen = len(wholeAPI['Features']) if len(wholeAPI['Features']) != 0 else 1
    counter = 0
    for feature in wholeAPI['Features']:
        if not feature['wrapped']:
            counter += feature['danger']
    average = counter / totalLen
    block = 1 if average >= treshold else 0
    return {'block': block, 'totalLen': totalLen, 'counter': counter }

def gen_wrappings(wrappers_dir, final_json, implement_top_n):
    if not os.path.exists(wrappers_dir):
        print("The specified path does not exist.")
        exit(1)
    if not os.path.exists(final_json):
        print("The specified path does not exist.")
        exit(1)
    with open(final_json, "r") as f:
        final = json.load(f)

def generate_common(common_dir: str, final_json: str, treshold: int = -100):
    if not os.path.exists(common_dir):
        print("The specified path does not exist.")
        exit(1)
    if not os.path.exists(final_json):
        print("The specified path does not exist.")
        exit(1)
    print("Generating common.js")
    # get all unimplemented apis
    finalJson = json.load(open(final_json, "r"))
    for api in finalJson:
        # which are not implemented
        unimplemented_apis = []
        for feature in finalJson[api]["Features"]:
            if feature['danger'] == None:
                feature['danger'] = 0
            if treshold == None:
                if not feature['wrapped']:
                    unimplemented_apis.append(feature['name'])
            elif not feature['wrapped'] and feature['danger'] >= treshold:
                unimplemented_apis.append(feature['name'])
        # check if wrappingS-<api>.js exists
        if len(unimplemented_apis) == 0:
            continue
        if not os.path.exists(f"{common_dir}/wrappingS-{api}.js"):
            text = generateWrapper_forGroup(unimplemented_apis)
            # names are api without .
            with open(f"{common_dir}/wrappingS-{api}.js", "w") as f:
                f.write(text)
        else:
            # check if the apis are already present
            generated = generateWrapper_forGroup(unimplemented_apis)
            with open(f"{common_dir}/wrappingS-{api}.js", "r") as f:
                if generated in f.read():
                    print("already present")
                    continue
            # if it exists, append the unimplemented apis to it
            with open(f"{common_dir}/wrappingS-{api}.js", "a") as f:
                f.write(generateWrapper_forGroup(unimplemented_apis))

    # generate groups to levels.js at line with // INSERT-ANCHOR
    to_insert = ""
    # settings has to contain api name and value 1 if average number of danger is greater than x
    settings = {}
    for api in finalJson:
        wrappers_to_insert = {}
        description2_ = {}
        for feature in finalJson[api]["Features"]:
            if feature['danger'] == None:
                feature['danger'] = 0
            try:
                if not feature['wrapped']:# and feature['danger'] >= treshold:
                    if not api in wrappers_to_insert:
                        wrappers_to_insert[api] = [feature['name']]
                    else:
                        wrappers_to_insert[api].append(feature['name'])

                    description2_[feature['name']] = {
                        "description": feature['description'],
                        "url": feature['url'],
                        # round danger to 2 decimal places
                        "danger": f"{round(feature['danger'] * 100, 2)} %"}
            except TypeError:
                print(f"TypeError: {feature}, {treshold}")
        wrapper_name = f"{finalJson[api]['API_class']}{finalJson[api]['catId']}"
        if not wrappers_to_insert == {}:
            settings[wrapper_name] = fillSettings(finalJson[api], 0.5)
            to_insert += generateGroup(
                # name_=f"{finalJson[api]['catId']}",
                name_=wrapper_name,
                label=finalJson[api]['API_class'],
                description=finalJson[api]['Description'],
                wrappers=wrappers_to_insert,
                description2=description2_)
    with open(f"{common_dir}/WEBAPI_levels.js", "w", encoding="utf-8") as f:
        f.write(to_insert)

    # replace "// ANCHOR" in levels.js with the generated groups
    print("Generating levels.js")
    with open (f"{common_dir}/levels.js", "r", encoding="utf-8") as f:
        content = f.read()

    if "// GENERATED" in content:
        content = content.replace(content[content.find("// GENERATED"):content.rfind("// GENERATED") + len("// GENERATED")], "// ANCHOR")
    content = content.replace("// ANCHOR", f"// GENERATED\n{to_insert}// GENERATED")
    
    experimental_variable = generateLevel(settings=settings, level_name="Experimental")
    # find and replace text between // EXPERIMENTAL tags with experimental_variable
    if "// EX" in content:
        content = content.replace(content[content.find("// EX"):content.rfind("// EX") + len("// EX")], "// EXPERIMENTAL")
    content = content.replace("// EXPERIMENTAL", f"// EX\n{experimental_variable}// EX")
    
    with open(f"{common_dir}/levels.js", "w", encoding="utf-8") as f:
        f.write(content)





def main():
    parser = argparse.ArgumentParser(
        prog="pythongen.py",
        description="Generate files for the webextension.",
    )
    parser.add_argument("--implemented_apis", help="Specify the path to the folder where wrapping*.js is located. Returns already wrapped apis.", type=str, default="")
    parser.add_argument("--all_apis", help="Specify the path to the folder where wrapping*.js is located. Returns already wrapped apis.", type=str, default="")
    parser.add_argument("--gen_wrappings", help="Generate wrapping*.js files from the json files in the specified folder.")
    parser.add_argument("--dir", help="Specify the path to the folder where wrapping*.js is located.", type=str, default="")
    parser.add_argument("--final", help="Specify the path to the file final.json.", type=str, default="")
    parser.add_argument("--common", help="specify the common directory", type=str)
    parser.add_argument("-o", "--output", help="Specify output directory", type=str)
    args = parser.parse_args()
    if args.output:
        if not os.path.exists(args.output):
            os.mkdir(args.output)
    if args.implemented_apis:
        apis = implemented_apis(args.implemented_apis)
        for api in apis:
            print(api)
    
    elif args.all_apis:
        apis = all_apis(args.all_apis)
        # save all apis to a json file
        with open(f"all_apis.json", "w") as f:
            json.dump(apis, f, indent=4)
    
    elif args.gen_wrappings and args.dir and args.final:
        gen_wrappings(args.dir, args.final, 5)
    
    
    elif args.common and args.final:
        print(args.common)
        # co má viac ako 50% blokovaných sa zablokuje
        common = generate_common(args.common, args.final, 0.1)
        print(common)
    else:
        print("No arguments specified. Use --help for more information.")


if __name__ == "__main__":
    main()


