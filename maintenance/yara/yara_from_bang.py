#!/usr/bin/env python3

# Binary Analysis Next Generation (BANG!)
#
# Copyright - Armijn Hemel, Tjaldur Software Governance Solutions
# Licensed under the terms of the GNU Affero General Public License version 3
# SPDX-License-Identifier: AGPL-3.0-only

'''
This script generates a YARA rule from a JSON file containing symbols
and strings that were extracted from a binary using BANG.

Use bang_to_json.py to generate the JSON file.
'''

import copy
import datetime
import json
import multiprocessing
import pathlib
import pickle
import queue
import re
import sys
import uuid

import packageurl
import click

# import YAML module for the configuration
from yaml import load
from yaml import YAMLError
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from yara_config import YaraConfig, YaraConfigException

# YARA escape sequences
ESCAPE = str.maketrans({'"': '\\"',
                        '\\': '\\\\',
                        '\t': '\\t',
                        '\n': '\\n'})

NAME_ESCAPE = str.maketrans({'.': '_',
                             '-': '_'})


def generate_yara(yara_file, metadata, functions, variables, strings,
                  tags, heuristics, fullword, yara_operator, bang_type):
    '''Generate YARA rules from identifiers and heuristics.
       Returns a UUID for a rule.'''
    generate_date = datetime.datetime.utcnow().isoformat()
    rule_uuid = uuid.uuid4()
    total_identifiers = len(functions) + len(variables) + len(strings)
    meta = f'''
    meta:
        description = "Rule for {metadata['name']}"
        author = "Generated by BANG"
        date = "{generate_date}"
        uuid = "{rule_uuid}"
        total_identifiers = "{total_identifiers}"
        identifiers_from = "{bang_type}"
'''

    for m in sorted(metadata):
        meta += f'        {m} = "{metadata[m]}"\n'

    # create a tags string for the rule if there are any tags.
    # These can be used by YARA to only run specific rules.
    tags_string = ''
    if tags != []:
        tags_string = ": " + " ".join(tags)

    rule = str(rule_uuid).translate(NAME_ESCAPE)
    rule_name = f'rule rule_{rule}{tags_string}\n'

    with yara_file.open(mode='w') as p:
        p.write(rule_name)
        p.write('{')
        p.write(meta)
        p.write('\n    strings:\n')

        num_strings = 0
        num_functions = 0
        num_variables = 0

        # First write all strings
        if strings != []:
            p.write("\n        // Extracted strings\n\n")
            counter = 1
            for s in strings:
                try:
                    s_translated = s.translate(ESCAPE)
                    p.write(f"        $string{counter} = \"{s_translated}\"{fullword}\n")
                    counter += 1
                except:
                    pass

        # Then write the functions
        if functions != []:
            p.write("\n        // Extracted functions\n\n")
            counter = 1
            for s in sorted(functions):
                p.write(f"        $function{counter} = \"{s}\"{fullword}\n")
                counter += 1

        # Then the variable names
        if variables != []:
            p.write("\n        // Extracted variables\n\n")
            counter = 1
            for s in sorted(variables):
                p.write(f"        $variable{counter} = \"{s}\"{fullword}\n")
                counter += 1

        # Finally write the conditions
        if len(strings) >= heuristics['strings_minimum_present']:
            num_strings = max(len(strings)//heuristics['strings_percentage'], heuristics['strings_matched'])
        else:
            num_strings = 'any'

        if len(functions) >= heuristics['functions_minimum_present']:
            num_funcs = max(len(functions)//heuristics['functions_percentage'], heuristics['functions_matched'])
        else:
            num_funcs = 'any'

        if len(variables) >= heuristics['variables_minimum_present']:
            num_vars = max(len(variables)//heuristics['variables_percentage'], heuristics['variables_matched'])
        else:
            num_vars = "any"

        p.write('\n    condition:\n')
        if strings != []:
            p.write(f'        {num_strings} of ($string*)')

            if not (functions == [] and variables == []):
                p.write(f' {yara_operator}\n')
            else:
                p.write('\n')
        if functions != []:
            p.write(f'        {num_funcs} of ($function*)')

            if variables != []:
                p.write(' %s\n' % yara_operator)
            else:
                p.write('\n')
        if variables != []:
            p.write(f'        {num_vars} of ($variable*)')
        p.write('\n}')

    # return the UUID for the rule so it can be recorded
    return rule_uuid

@click.group()
def app():
    pass

@app.command(short_help='process a BANG JSON result file and output YARA rules for binaries')
@click.option('--config-file', '-c', required=True, help='configuration file',
              type=click.File('r'))
@click.option('--json', '-j', 'result_json', help='BANG JSON result file',
              type=click.File('r'), required=True)
@click.option('--identifiers', '-i', help='pickle with low quality identifiers',
              required=True, type=click.File('rb'))
@click.option('--no-functions', is_flag=True, default=False, help="do not use functions")
@click.option('--no-variables', is_flag=True, default=False, help="do not use variables")
@click.option('--no-strings', is_flag=True, default=False, help="do not use strings")
def binary(config_file, result_json, identifiers, no_functions, no_variables, no_strings):
    bang_type = 'binary'

    # define a data structure with low quality
    # identifiers for ELF and Dex
    lq_identifiers = {'elf': {'functions': [], 'variables': [], 'strings': []},
                      'dex': {'functions': [], 'variables': [], 'strings': []}}

    # read the pickle with low quality identifiers
    if identifiers is not None:
        try:
            lq_identifiers = pickle.load(identifiers)
        except pickle.UnpicklingError:
            pass

    # parse the configuration
    yara_config = YaraConfig(config_file)
    yara_env = yara_config.parse()

    yara_directory = yara_env['yara_directory'] / 'binary'

    yara_directory.mkdir(exist_ok=True)

    # ignore object files (regular and GHC specific)
    ignored_elf_suffixes = ['.o', '.p_o']

    # load the JSON
    try:
        bang_data = json.load(result_json)
    except:
        print("Could not open JSON, exiting", file=sys.stderr)
        sys.exit(1)

    if 'labels' in bang_data:
        if 'ocaml' in bang_data['labels']:
            if yara_env['ignore_ocaml']:
                print("OCAML file found that should be ignored, exiting", file=sys.stderr)
                sys.exit()
        if 'elf' in bang_data['labels']:
            suffix = pathlib.Path(bang_data['metadata']['name']).suffix

            if suffix in ignored_elf_suffixes:
                print("Ignored suffix, exiting", file=sys.stderr)
                sys.exit()

            if 'static' in bang_data['labels']:
                if not 'linuxkernelmodule' in bang_data['labels']:
                    # TODO: clean up for linux kernel modules
                    print("Static ELF binary not supported yet, exiting", file=sys.stderr)
                    sys.exit()

    if bang_data['metadata']['sha256'] == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855':
        print("Cannot generate YARA file for empty file, exiting", file=sys.stderr)
        sys.exit(1)

    tags = bang_data.get('tags', [])

    # expand yara_env with binary scanning specific values
    yara_env['lq_identifiers'] = lq_identifiers

    # store the type of executable
    if 'elf' in bang_data['labels']:
        exec_type = 'elf'
    elif 'dex' in bang_data['labels']:
        exec_type = 'dex'
    else:
        exec_type = None

    if not exec_type:
        print("Unsupported executable type, exiting", file=sys.stderr)
        sys.exit(2)

    # set metadata
    metadata = bang_data['metadata']

    strings = set()

    heuristics = yara_env['heuristics']

    if exec_type == 'elf':
        functions = set()
        variables = set()

        if 'telfhash' in bang_data['metadata']:
            metadata['telfhash'] = bang_data['metadata']['telfhash']

        # process strings
        if bang_data['strings'] != [] and not no_strings:
            for s in bang_data['strings']:
                if len(s) < yara_env['string_min_cutoff']:
                    continue
                if len(s) > yara_env['string_max_cutoff']:
                    continue
                # ignore whitespace-only strings
                if re.match(r'^\s+$', s) is None:
                    if s in yara_env['lq_identifiers']['elf']['strings']:
                        continue
                    strings.add(s.translate(ESCAPE))

        # process symbols, split in functions and variables
        if bang_data['symbols'] != []:
            for s in bang_data['symbols']:
                if s['section_index'] == 0:
                    continue
                if yara_env['ignore_weak_symbols']:
                    if s['binding'] == 'weak':
                        continue
                if len(s['name']) < yara_env['identifier_cutoff']:
                    continue
                if '@@' in s['name']:
                    identifier_name = s['name'].rsplit('@@', 1)[0]
                elif '@' in s['name']:
                    identifier_name = s['name'].rsplit('@', 1)[0]
                else:
                    identifier_name = s['name']
                if s['type'] == 'func' and not no_functions:
                    if identifier_name in yara_env['lq_identifiers']['elf']['functions']:
                        continue
                    functions.add(identifier_name)
                elif s['type'] == 'object' and not no_variables:
                    if identifier_name in yara_env['lq_identifiers']['elf']['variables']:
                        continue
                    variables.add(identifier_name)

        # check if the number of identifiers passes a threshold.
        # If not assume that there are no identifiers.
        if len(strings) < heuristics['strings_extracted']:
            strings = set()
        if len(functions) < heuristics['functions_extracted']:
            functions = set()
        if len(variables) < heuristics['variables_extracted']:
            variables = set()

        yara_tags = sorted(set(tags + ['elf']))
    elif exec_type == 'dex':
        functions = set()
        variables = set()

        for c in bang_data['classes']:
            # process methods/functions
            if not no_functions:
                for method in c['methods']:
                    # ignore whitespace-only methods
                    if len(method['name']) < yara_env['identifier_cutoff']:
                        continue
                    if re.match(r'^\s+$', method['name']) is not None:
                        continue
                    if method['name'] in ['<init>', '<clinit>']:
                        continue
                    if method['name'].startswith('access$'):
                        continue
                    if method['name'] in yara_env['lq_identifiers']['dex']['functions']:
                        continue
                    functions.add(method['name'])

            # process strings
            if not no_strings:
                for method in c['methods']:
                    for s in method['strings']:
                        if len(s) < yara_env['string_min_cutoff']:
                            continue
                        if len(s) > yara_env['string_max_cutoff']:
                            continue
                        # ignore whitespace-only strings
                        if re.match(r'^\s+$', s) is None:
                            strings.add(s.translate(ESCAPE))

            # process fields/variables
            if not no_variables:
                for field in c['fields']:
                    # ignore whitespace-only methods
                    if len(field['name']) < yara_env['identifier_cutoff']:
                        continue
                    if re.match(r'^\s+$', field['name']) is not None:
                        continue

                    if field['name'] in yara_env['lq_identifiers']['dex']['variables']:
                        continue
                    variables.add(field['name'])

        yara_tags = sorted(set(tags + ['dex']))

    # do not generate a YARA file if there is no data
    if strings == set() and variables == set() and functions == set():
        return

    total_identifiers = len(functions) + len(variables) + len(strings)

    # by default YARA has a limit of 10,000 identifiers
    # TODO: see which ones can be ignored.
    if total_identifiers > yara_env['max_identifiers']:
        pass

    yara_file = yara_directory / (f"{metadata['name']}-{metadata['sha256']}.yara")

    fullword = ''
    if yara_env['fullword']:
        fullword = ' fullword'

    rule_uuid = generate_yara(yara_file, metadata, sorted(functions), sorted(variables),
                              sorted(strings), yara_tags, heuristics, fullword,
                              yara_env['operator'], bang_type)

def process_identifiers(process_queue, result_queue, json_directory,
                        yara_directory, yara_env, tags, bang_type):
    '''Read a JSON result file with identifiers extracted from source code,
       clean up and generate YARA rules'''
    heuristics = yara_env['heuristics']

    fullword = ''
    if yara_env['fullword']:
        fullword = ' fullword'

    while True:
        json_file = process_queue.get()

        with open(json_file, 'r') as json_archive:
            identifiers = json.load(json_archive)

        identifiers_per_language = {}
        language = identifiers['metadata']['language']

        identifiers_per_language[language] = {}
        identifiers_per_language[language]['strings'] = set()
        identifiers_per_language[language]['functions'] = set()
        identifiers_per_language[language]['variables'] = set()

        for string in identifiers['strings']:
            if len(string) >= yara_env['string_min_cutoff'] and len(string) <= yara_env['string_max_cutoff']:
                if language == 'c':
                    if string in yara_env['lq_identifiers']['elf']['strings']:
                        continue
                identifiers_per_language[language]['strings'].add(string)

        for function in identifiers['functions']:
            if len(function) < yara_env['identifier_cutoff']:
                continue
            if language == 'c':
                if function in yara_env['lq_identifiers']['elf']['functions']:
                    continue
            identifiers_per_language[language]['functions'].add(function)

        for variable in identifiers['variables']:
            if len(variable) < yara_env['identifier_cutoff']:
                continue
            if language == 'c':
                if variable in yara_env['lq_identifiers']['elf']['variables']:
                    continue
            identifiers_per_language[language]['variables'].add(variable)

        for language in identifiers_per_language:
            metadata = identifiers['metadata']
            metadata['name'] = metadata['archive']

            strings = sorted(identifiers_per_language[language]['strings'])
            variables = sorted(identifiers_per_language[language]['variables'])
            functions = sorted(identifiers_per_language[language]['functions'])

            if not (strings == [] and variables == [] and functions == []):
                yara_tags = sorted(set(tags + [language]))
                yara_file = yara_directory / (f"{metadata['archive']}-{metadata['language']}.yara")
                rule_uuid = generate_yara(yara_file, metadata, functions, variables, strings,
                                          yara_tags, heuristics, fullword,
                                          yara_env['operator'], bang_type)

        result_meta = {}
        for language in identifiers_per_language:
            result_meta[language] = {}
            result_meta[language]['strings'] = len(identifiers_per_language[language]['strings'])
            result_meta[language]['variables'] = len(identifiers_per_language[language]['variables'])
            result_meta[language]['functions'] = len(identifiers_per_language[language]['functions'])

        result_queue.put(result_meta)
        process_queue.task_done()


@app.command(short_help='process JSON files with identifiers extracted from source code and output YARA rules')
@click.option('--config-file', '-c', required=True, help='configuration file',
              type=click.File('r'))
@click.option('--json-directory', '-j', required=True, help='JSON file directory',
              type=click.Path(exists=True))
@click.option('--identifiers', '-i', required=True, help='pickle with low quality identifiers',
              type=click.File('rb'))
@click.option('--meta', '-m', required=True, help='file with meta information about a package',
              type=click.File('r'))
@click.option('--no-functions', is_flag=True, default=False, help="do not use functions")
@click.option('--no-variables', is_flag=True, default=False, help="do not use variables")
@click.option('--no-strings', is_flag=True, default=False, help="do not use strings")
def source(config_file, json_directory, identifiers, meta, no_functions, no_variables, no_strings):
    bang_type = "source"
    json_directory = pathlib.Path(json_directory)

    # should be a real directory
    if not json_directory.is_dir():
        print(f"{json_directory} is not a directory, exiting.", file=sys.stderr)
        sys.exit(1)

    # parse the configuration
    yara_config = YaraConfig(config_file)
    try:
        yara_env = yara_config.parse()
    except YaraConfigException as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    # parse the package meta information
    try:
        package_meta_information = load(meta, Loader=Loader)
    except (YAMLError, PermissionError) as e:
        print("invalid YAML:", e.args, file=sys.stderr)
        sys.exit(1)

    packages = []

    package = package_meta_information['package']

    # first verify that the top level package url is valid
    try:
        top_purl = packageurl.PackageURL.from_string(package_meta_information['packageurl'])
    except ValueError:
        print(f"{package_meta_information['packageurl']} not a valid packageurl", file=sys.stderr)
        sys.exit(1)

    versions = set()

    for release in package_meta_information['releases']:
        for version in release:
            # verify that the version is a valid package url
            try:
                purl = packageurl.PackageURL.from_string(version)
            except ValueError:
                print(f"{version} not a valid packageurl", file=sys.stderr)
                if yara_env['error_fatal']:
                    sys.exit(1)
                continue
            # sanity checks to verify that the top level purl matches
            if purl.type != top_purl.type:
                print(f"type '{purl.type}' does not match top level type '{top_purl.type}'",
                      file=sys.stderr)
                if yara_env['error_fatal']:
                    sys.exit(1)
                continue
            if purl.name != top_purl.name:
                print(f"name '{purl.name}' does not match top level name '{top_purl.name}'",
                      file=sys.stderr)
                if yara_env['error_fatal']:
                    sys.exit(1)
                continue
            versions.add(version)

    # store the languages
    languages = set()

    # process all the JSON files in the directory
    for result_file in json_directory.glob('**/*'):
        # sanity check for the package
        try:
            with open(result_file, 'r') as json_archive:
                json_results = json.load(json_archive)

            languages.add(json_results['metadata']['language'])

            if json_results['metadata']['package'] == package:
                if json_results['metadata'].get('packageurl') in versions:
                    packages.append(result_file)
        except Exception as e:
            continue

    # mapping for low quality identifiers. C is mapped to ELF,
    # Java is mapped to Dex. TODO: use something a bit more sensible.
    lq_identifiers = {'elf': {'functions': [], 'variables': [], 'strings': []},
                      'dex': {'functions': [], 'variables': [], 'strings': []}}

    # read the pickle with identifiers
    if identifiers is not None:
        try:
            lq_identifiers = pickle.load(identifiers)
        except pickle.UnpicklingError:
            pass

    yara_directory = yara_env['yara_directory'] / 'src' / top_purl.type / top_purl.name

    yara_directory.mkdir(parents=True, exist_ok=True)

    tags = ['source']

    # expand yara_env with source scanning specific values
    yara_env['lq_identifiers'] = lq_identifiers

    process_manager = multiprocessing.Manager()

    # create a queue for scanning files
    process_queue = process_manager.JoinableQueue(maxsize=0)
    result_queue = process_manager.JoinableQueue(maxsize=0)
    processes = []

    # walk the archives directory
    for json_file in packages:
        json_results = json_directory / json_file
        process_queue.put(json_results)

    # create processes for unpacking archives
    for i in range(0, yara_env['threads']):
        process = multiprocessing.Process(target=process_identifiers,
                                          args=(process_queue, result_queue, json_directory,
                                                yara_directory, yara_env, tags, bang_type))
        processes.append(process)

    # start all the processes
    for process in processes:
        process.start()

    process_queue.join()

    # Done processing, terminate processes
    for process in processes:
        process.terminate()

    # store the minimum per language, relevant for heuristics
    min_per_language = {}
    for language in languages:
        min_per_language[language] = {}
        min_per_language[language]['strings'] = sys.maxsize
        min_per_language[language]['variables'] = sys.maxsize
        min_per_language[language]['functions'] = sys.maxsize

    while True:
        try:
            result = result_queue.get_nowait()
            for language in result:
                for identifier in ['strings', 'functions', 'variables']:
                    min_per_language[language][identifier] = min(min_per_language[language][identifier], result[language][identifier])
                result_queue.task_done()
        except queue.Empty:
            break

    # block until the result queue is empty
    result_queue.join()

    fullword = ''
    if yara_env['fullword']:
        fullword = ' fullword'

    # Now generate the top level YARA file. This requires a new yara directory
    yara_directory = yara_env['yara_directory'] / 'src' / top_purl.type

    # TODO: sort the packages based on version number
    for language in languages:
        # read the JSON again, this time aggregate the data
        all_strings_union = set()
        all_strings_intersection = set()

        all_functions_union = set()
        all_functions_intersection = set()

        all_variables_union = set()
        all_variables_intersection = set()

        website = ''
        cpe = ''
        cpe23 = ''

        # keep track of if the first element is being processed
        is_start = True

        for package in packages:
            with open(package, 'r') as json_archive:
                json_results = json.load(json_archive)

                if website == '':
                    website = json_results['metadata']['website']

                if cpe == '':
                    cpe = json_results['metadata']['cpe']
                if cpe23 == '':
                    cpe23 = json_results['metadata']['cpe23']

                strings = set()

                for string in json_results['strings']:
                    if len(string) >= yara_env['string_min_cutoff'] and len(string) <= yara_env['string_max_cutoff']:
                        if language == 'c':
                            if string in yara_env['lq_identifiers']['elf']['strings']:
                                continue
                        strings.add(string)

                functions = set()

                for function in json_results['functions']:
                    if len(function) < yara_env['identifier_cutoff']:
                        continue
                    if language == 'c':
                        if function in yara_env['lq_identifiers']['elf']['functions']:
                            continue
                    functions.add(function)

                variables = set()
                for variable in json_results['variables']:
                    if len(variable) < yara_env['identifier_cutoff']:
                        continue
                    if language == 'c':
                        if variable in yara_env['lq_identifiers']['elf']['variables']:
                            continue
                    variables.add(variable)

                all_strings_union.update(strings)
                all_functions_union.update(functions)
                all_variables_union.update(variables)

                if is_start:
                    all_strings_intersection.update(strings)
                    all_functions_intersection.update(functions)
                    all_variables_intersection.update(variables)
                    is_start = False
                else:
                    all_strings_intersection &= strings
                    all_functions_intersection &= functions
                    all_variables_intersection &= variables

        # sort the identifiers so they are printed in
        # sorted order in the YARA rule as well
        strings = sorted(all_strings_union)
        variables = sorted(all_variables_union)
        functions = sorted(all_functions_union)

        # adapt the heuristics based on the minimum amount of strings
        # found in a package.

        # first instantiate the heuristics
        heuristics = copy.deepcopy(yara_env['heuristics'])

        # then change the percentage based on the minimum
        # amount of identifiers, and the union
        heuristics['strings_percentage'] = min(heuristics['strings_percentage'],
                                               heuristics['strings_percentage'] * min_per_language[language]['strings'] / len(strings))
        heuristics['functions_percentage'] = min(heuristics['functions_percentage'],
                                                heuristics['functions_percentage'] * min_per_language[language]['functions'] / len(functions))
        heuristics['variables_percentage'] = min(heuristics['variables_percentage'],
                                                 heuristics['variables_percentage'] * min_per_language[language]['variables'] / len(variables))

        # finally generate union and intersection files
        # that operate on all versions of a package
        archive_name = f'{top_purl.name}-union'
        metadata = {'archive': archive_name, 'name': archive_name, 'language': language,
                    'package': top_purl.name, 'packageurl': top_purl,
                    'website': website, 'cpe': cpe, 'cpe23': cpe23}

        if not (strings == [] and variables == [] and functions == []):
            yara_file = yara_directory / (f"{metadata['archive']}-{metadata['language']}.yara")
            yara_tags = sorted(set(tags + [language]))
            rule_uuid = generate_yara(yara_file, metadata, functions, variables, strings,
                                      yara_tags, heuristics, fullword,
                                      yara_env['operator'], bang_type)

        strings = sorted(all_strings_intersection)
        variables = sorted(all_variables_intersection)
        functions = sorted(all_functions_intersection)

        # reset heuristics
        heuristics = copy.deepcopy(yara_env['heuristics'])

        archive_name = f'{top_purl.name}-intersection'
        metadata = {'archive': archive_name, 'name': archive_name, 'language': language,
                    'package': top_purl.name, 'packageurl': top_purl,
                    'website': website, 'cpe': cpe, 'cpe23': cpe23}

        if not (strings == [] and variables == [] and functions == []):
            yara_file = yara_directory / (f"{metadata['archive']}-{metadata['language']}.yara")

            yara_tags = sorted(set(tags + [language]))
            rule_uuid = generate_yara(yara_file, metadata, functions, variables, strings,
                                      yara_tags, heuristics, fullword,
                                      yara_env['operator'], bang_type)


if __name__ == "__main__":
    app()
