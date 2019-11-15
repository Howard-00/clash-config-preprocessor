import requests
import utils
import yaml
import re

from collections import OrderedDict


def handle_v1(data: OrderedDict) -> OrderedDict:
    preprocessor: OrderedDict = data["preprocessor"]

    if preprocessor is None or preprocessor["version"] != 1:
        raise utils.ParseException("Version != 1")

    result: OrderedDict = OrderedDict()

    general_block: OrderedDict = data["clash-general"]
    result.update(general_block)

    proxy_sources_dicts: list = data["proxy-sources"]
    proxies: list = []

    for item in proxy_sources_dicts:
        proxies += load_proxies(item)

    proxy_group_dispatch_dicts: list = data["proxy-group-dispatch"]
    proxy_groups: list = []

    for item in proxy_group_dispatch_dicts:
        group_data: OrderedDict = item.copy()
        ps: list = []

        black_regex = re.compile(item["proxies-filters"]["black-regex"])
        white_regex = re.compile(item["proxies-filters"]["white-regex"])

        flat_proxies: set = set()
        back_flat_proxies: set = set()
        if "flat-proxies" in item and item["flat-proxies"] is not None:
            flat_proxies = set(item['flat-proxies'])
        if "back-flat-proxies" in item and item["back-flat-proxies"] is not None:
            back_flat_proxies = set(item['back-flat-proxies'])
        for p in proxies:
            p_name: str = p["name"]
            if white_regex.fullmatch(p_name) and not black_regex.fullmatch(p_name) and p_name not in flat_proxies and p_name not in back_flat_proxies:
                ps.append(p_name)


        group_data.pop("proxies-filters", None)
        group_data.pop("flat-proxies", None)
        group_data.pop("back-flat-proxies", None)

        group_data["proxies"] = list(flat_proxies) + ps + list(back_flat_proxies)

        proxy_groups.append(group_data)

    rule_sets_dicts: list = data["rule-sets"]
    rule_sets: dict = {}

    if not rule_sets_dicts is None:
        for item in rule_sets_dicts:
            item_name: str = item["name"]
            item_type: str = item["type"]
            item_map: dict = {}
            item_rule_skip = item.get("rule-skip", {})
            item_target_skip = item.get("target-skip", {})
            for target_map_element in item.get("target-map", {}):
                kv: list = target_map_element.split(",")
                item_map[kv[0]] = kv[1]

            if item_type == "url":
                rule_sets[item_name] = load_url_rule_set(
                    item["url"], item_map, item_rule_skip, item_target_skip)
            elif item_type == "file":
                rule_sets[item_name] = load_file_rule_set(
                    item["path"], item_map, item_rule_skip, item_target_skip)

    rules: list = []

    for rule in data["rule"]:
        if str(rule).startswith("RULE-SET"):
            rules.extend(rule_sets[str(rule).split(",")[1]])
        else:
            rules.append(rule)

    result["Proxy"] = proxies
    result["Proxy Group"] = proxy_groups
    result["Rule"] = rules

    return result


def load_proxies(item):
    if item["type"] == 'plain':
        return [item['data']]
    if item["type"] == 'url':
        data = requests.get(item['url'])
        data_yaml: OrderedDict = yaml.load(
            data.content.decode(), Loader=yaml.Loader)
    else:
        with open(item['path'], "r") as f:
            data_yaml: OrderedDict = yaml.load(f, Loader=yaml.Loader)
    proxy_yaml = data_yaml['Proxy']
    for p in proxy_yaml:
        if 'udp' in item and 'udp' not in p:
            p['udp'] = item['udp']
        if 'prefix' in item:
            p['name'] = item['prefix'] + p['name']
        if 'suffix' in item:
            p['name'] += item['suffix']
        if p['type'] == 'ss':
            if 'plugin' in item and 'plugin' not in p:
                p['plugin'] = item['plugin']
                if 'plugin-opts' in item:
                    p['plugin-opts'] = item['plugin-opts']
    return proxy_yaml

def load_url_rule_set(url: str, targetMap: dict, skipRule: set, skipTarget: set) -> list:
    data = yaml.load(requests.get(url).content, Loader=yaml.Loader)
    result: list = []

    for rule in data["Rule"]:
        original_target = str(rule).split(",")[-1]
        map_to: str = targetMap.get(original_target)
        if str(rule).split(',')[0] not in skipRule and original_target not in skipTarget:
            if not map_to is None:
                result.append(str(rule).replace(original_target, map_to))
            else:
                result.append(str(rule))

    return result


def load_file_rule_set(path: str, targetMap: dict, skipRule: set, skipTarget: set) -> list:
    with open(path, "r") as f:
        data = yaml.load(f, Loader=yaml.Loader)
    result: list = []

    for rule in data["Rule"]:
        original_target = str(rule).split(",")[-1]
        map_to: str = targetMap.get(original_target)
        if str(rule).split(',')[0] not in skipRule and original_target not in skipTarget:
            if not map_to is None:
                result.append(str(rule).replace(original_target, map_to))
            else:
                result.append(rule)

    return result
