import pandas as pd
from collections import OrderedDict
import json
import sys

data_frame = None
values = {}
last_key = None
interval = False
primary_key = None
first_run = True
temp_array = []


def normalize_json_to_tabular_format(path_of_file):
    with open(path_of_file) as file:
        data = file.read().replace('\n', '')
    j_data = json.loads(data, object_pairs_hook=OrderedDict)
    convert_to_tabular_format(j_data)


def convert_to_tabular_format(data, key=None):

    global last_key

    if isinstance(data, dict):
        for k in data.keys():
            convert_to_tabular_format(data[k], k if key is None else key + '.' + k)

    elif isinstance(data, str) or isinstance(data, int) or isinstance(data, bool) \
            or isinstance(data, float) or isinstance(data, type(None)):
        create_dict_with_values(key, data if data is not None else '')

    elif isinstance(data, list):
        for element in data:
            last_key = key
            convert_to_tabular_format(element, key)

    else:
        print(type(data), key)
        raise Exception('Unknown data type')


def create_dict_with_values(key, data):
    global last_key
    global interval
    global primary_key
    global temp_array

    primary_key = key if primary_key is None else primary_key
    if not first_run:
        temp_array.append(key)

        '''
            to idenify if tags are added at later stage which have never seen before
            known issue need to work on it
        '''
        # for temp in temp_array:
        #     if temp not in values:
        #         values[temp] = ['No value found']
        #         if record_max_length() > 2:
        #             for i in range(record_max_length() - 1):
        #                 values[temp].append('No value found')

    if key == primary_key:
        check_copy_values_to_last_level_tags()

    if key in values:
        if last_key == key:
            if interval:
                values[key].append(data)
            else:
                last_item = values[key][-1]
                values[key] = values[key][:-1] + [str(last_item) + ', ' + str(data)]
            interval = False
        else:
            values[key].append(data)
            last_key = None
            interval = True
    else:
        values[key] = [data]


def check_copy_values_to_last_level_tags():
    global first_run
    global temp_array

    max_length = record_max_length()

    if not first_run:
        for key in values:
            if key not in temp_array:
                values[key].append('No value found')

    for key in values:
        if len(values[key]) < max_length:
            short_by = max_length - len(values[key])
            for i in range(short_by):
                values[key].append(values[key][-1])

    if first_run:
        first_run = False

    temp_array = []


def record_max_length():
    max_length = 0

    for key in values:
        max_length = len(values[key]) if len(values[key]) > max_length else max_length

    return max_length


def main(args):
    global data_frame
    global temp_array
    global primary_key
    if len(args) < 2:
        print('Source and Destination file name and path required')
        sys.exit(0)
    else:
        data = args[0]
        normalize_json_to_tabular_format(data)
        temp_array.append(primary_key)
        check_copy_values_to_last_level_tags()
        data_frame = pd.DataFrame.from_dict(values, orient='index')
        data_frame = data_frame.transpose()
        data_frame.to_csv(args[1])


if __name__ == '__main__':
    main(sys.argv[1:])