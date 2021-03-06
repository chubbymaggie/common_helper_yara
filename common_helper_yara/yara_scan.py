from subprocess import check_output, CalledProcessError, STDOUT
import sys
import re
import json
import logging

from .common import convert_external_variables


def scan(signature_path, file_path, external_variables={}, recursive=False):
    '''
    Scan files and return matches

    :param signature_path: path to signature file
    :type signature_path: string
    :param file_path: files to scan
    :type file_path: string
    :return: dict
    '''
    variables = convert_external_variables(external_variables)
    recursive = '-r' if recursive else ''
    try:
        scan_result = check_output("yara {} {} --print-meta --print-strings {} {}".format(variables, recursive, signature_path, file_path), shell=True, stderr=STDOUT)
    except CalledProcessError as e:
        logging.error("There seems to be an error in the rule file:\n{}".format(e.output.decode()))
        return {}
    try:
        return _parse_yara_output(scan_result.decode())
    except Exception as e:
        logging.error('Could not parse yara result: {} {}'.format(sys.exc_info()[0].__name__, e))
        return {}


def _parse_yara_output(output):
    resulting_matches = dict()

    match_blocks, rules = _split_output_in_rules_and_matches(output)

    matches_regex = re.compile(r'((0x[a-f0-9]*):(\S+):\s(.+))+')
    for index, rule in enumerate(rules):
        for match in matches_regex.findall(match_blocks[index]):
            _append_match_to_result(match, resulting_matches, rule)

    return resulting_matches


def _split_output_in_rules_and_matches(output):
    split_regex = re.compile(r'\n*.*\[.*\]\s\/.+\n*')
    match_blocks = split_regex.split(output)
    while '' in match_blocks:
        match_blocks.remove('')

    rule_regex = re.compile(r'(.*)\s\[(.*)\]\s([\.\.\/]|[\/]|[\.\/])(.+)')
    rules = rule_regex.findall(output)

    assert len(match_blocks) == len(rules)
    return match_blocks, rules


def _append_match_to_result(match, resulting_matches, rule):
    assert len(rule) == 4
    rule_name, meta_string, _, _ = rule
    assert len(match) == 4
    _, offset, matched_tag, matched_string = match

    meta_dict = _parse_meta_data(meta_string)

    this_match = resulting_matches[rule_name] if rule_name in resulting_matches else dict(rule=rule_name, matches=True, strings=list(), meta=meta_dict)

    this_match['strings'].append((int(offset, 16), matched_tag, matched_string.encode()))
    resulting_matches[rule_name] = this_match


def _parse_meta_data(meta_data_string):
    '''
    Will be of form 'item0=lowercaseboolean0,item1="value1",item2=value2,..'
    '''
    meta_data = dict()
    for item in meta_data_string.split(','):
        if '=' in item:
            key, value = item.split('=', maxsplit=1)
            value = json.loads(value) if value in ['true', 'false'] else value.strip('\"')
            meta_data[key] = value
        else:
            logging.warning('Malformed meta string \'{}\''.format(meta_data_string))
    return meta_data
