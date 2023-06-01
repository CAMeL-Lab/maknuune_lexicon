import re
from tqdm import tqdm

import gspread
from numpy import nan
import pandas as pd

import utils

from camel_tools.utils.charmap import CharMapper

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

diacritics_no_gem_bw = "aoiFNK"
diacritics_no_gem_ar = bw2ar(diacritics_no_gem_bw)

diac_remove_regex = re.compile(f'[{diacritics_no_gem_ar}]')

lexicon_sheets = ['Alif-Kha', 'Dal-Shin', 'Sad-Qaf', 'Kaf-Ya']

pacl_old = utils.read_pacl_as_df('data_v0', [f'{s}-COPY' for s in lexicon_sheets])
pacl = utils.read_pacl_as_df()
all_phrases_old = set([diac_remove_regex.sub('', p) for p in pacl_old[pacl_old['ANALYSIS'] == 'PHRASE']['FORM'].values.tolist()])

def _preprocess(x):
    return diac_remove_regex.sub('', x).replace(' ', '')

# columns_to_fix = ['مثال الاستخدام', 'الكلمة المقابلة بالفصحى']
columns_to_fix = ['FORM']

pacl = {'old': pacl_old, 'new': pacl}
lookup_tables = {}
for col_name in columns_to_fix:
    for version in ['old', 'new']:
        examples = lookup_tables.setdefault(col_name, {}).setdefault(version, {})
        for e in pacl[version][col_name].values.tolist():
            examples.setdefault(_preprocess(e), set()).add(e)

if 'الكلمة المقابلة بالفصحى' in lookup_tables:
    lookup_tables['الكلمة المقابلة بالفصحى']['old'] = {
        k: v for k, v in lookup_tables['الكلمة المقابلة بالفصحى']['old'].items() if any(' ' in vv.strip() for vv in v)}

if 'FORM' in lookup_tables:
    lookup_tables['FORM']['old'] = {
        k: v for k, v in lookup_tables['FORM']['old'].items() if any(' ' in vv.strip() for vv in v)}


def fix_mistake(lexicon):
    data = []
    total = len(lexicon.index)
    for i, row in tqdm(lexicon.iterrows(), total=total):
        for col_name in columns_to_fix:
            if not row[col_name].strip():
                continue
            header = list(lexicon.columns)
            status_column_index = header.index(col_name)
            col_letter = (chr(ord('A') + status_column_index // 27) if status_column_index >= 26 else '') + \
                chr(ord('A') + status_column_index % 26)
            ex_row_dediac_no_space = _preprocess(row[col_name])
            retrieved = lookup_tables[col_name]['old'].get(ex_row_dediac_no_space)
            if retrieved:
                retrieved = list(retrieved)
                if len(retrieved) == 1:
                    if retrieved[0] == row[col_name] or row[col_name].count(' ') == retrieved[0].count(' '):
                        continue
                    correct_index = 0
                else:
                    broke = False
                    for j, r in enumerate(retrieved):
                        if r == row[col_name] or row[col_name].count(' ') == r.count(' '):
                            print('Already exists... exiting.')
                            broke = True
                            break
                        print(j, ': ', ar2bw(r))
                    if broke:
                        continue
                    correct_index = int(input('Choose index of correct one: '))
                data.append({'range': f'{col_letter}{i + 2}', 'values': [[retrieved[correct_index]]]})
    
    return data


sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
sh = sa.open('PACL-Letter-Split')

for sheet_name in tqdm(utils.sheet_names):
    sheet = sh.worksheet(sheet_name)
    lexicon = pd.DataFrame(sheet.get_all_records()).astype(str)
    lexicon = lexicon.replace(nan, '', regex=True)
    data = fix_mistake(lexicon)
    if data:
        sheet.batch_update(data)

pass