from string import Template

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
    return wrapper.substitute(parent_object=parent_object, parent_object_property=parent_object_property, function_=function_, wrapped_name=wrapped_name)


def generateWrapper_forGroup(apis: list):
    wrapper = Template('''
(function() {
	var wrappers = [
		$wrapper
	];
	add_wrappers(wrappers);
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
    return group.substitute(name=name_.strip(), label=label.strip(), description=description.replace('\n', ' ').replace('"', "'").strip(), description2=description2_, wrappers=parsed_wrappers)



def generateLevel(settings: dict, level_name: str ):
    entry = f"""var {level_name} = {'{'}
	"builtin": true,
	"level_id": L_EXPERIMENTAL,
	"level_text": "Experimental",
	"level_description": "Strict level protections with additional wrappers enabled (including APIs known to regularly break webpages and APIs that do not work perfectly). Use this level if you want to experiment with JShelter. Use Recommended or Strict level with active Fingerprint Detector for your regular activities.",
"""
    for setting in settings:
        entry += f'\t"{setting}": {settings[setting]["block"]},\n'
    entry += "};"
    return entry

if __name__ == "__main__":
    apis = ["Array.prototype.push", "Array.prototype.pop"] #, "Array.prototype.shift", "Array.prototype.unshift", "Array.prototype.slice", "Array.prototype.splice", "Array.prototype.concat", "Array.prototype.join", "Array.prototype.reverse", "Array.prototype.sort", "Array.prototype.indexOf", "Array.prototype.lastIndexOf", "Array.prototype.every", "Array.prototype.some", "Array.prototype.forEach", "Array.prototype.map", "Array.prototype.filter", "Array.prototype.reduce", "Array.prototype.reduceRight", "Array.prototype.find", "Array.prototype.findIndex", "Array.prototype.includes", "Array.prototype.flat", "Array.prototype.flatMap", "Array.prototype.copyWithin", "Array.prototype.at", "Array.prototype.values", "Array.prototype.keys", "Array.prototype.entries"]
    wrapper = generateWrapper_forGroup(apis)
    with open("wrapper.js", "w") as f:
        f.write(wrapper)

    group = generateGroup(
        name="htmlcanvaselement",
        label="Localy rendered images",
        description="Protect against canvas fingerprinting.",
        wrappers={
            "H-C": [
                "CanvasRenderingContext2D.prototype.getImageData",
				"HTMLCanvasElement.prototype.toBlob",
				"HTMLCanvasElement.prototype.toDataURL",
				"OffscreenCanvas.prototype.convertToBlob",
				"CanvasRenderingContext2D.prototype.isPointInStroke",
				"CanvasRenderingContext2D.prototype.isPointInPath",
				"WebGLRenderingContext.prototype.readPixels",
				"WebGL2RenderingContext.prototype.readPixels",
                ],
            "AUDIO": [
                "AudioBuffer.prototype.getChannelData",
				"AudioBuffer.prototype.copyFromChannel",
				"AnalyserNode.prototype.getByteTimeDomainData",
				"AnalyserNode.prototype.getFloatTimeDomainData",
				"AnalyserNode.prototype.getByteFrequencyData",
				"AnalyserNode.prototype.getFloatFrequencyData"]},
        description2="",
    )
    with open("group.js", "w") as f:
        f.write(group)