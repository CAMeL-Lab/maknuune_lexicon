from bisect import bisect
from tqdm import tqdm
import time
import pickle
import os

import pandas as pd
from numpy import nan
import gspread
from camel_tools.utils.charmap import CharMapper

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

valid_radicals_ar = bw2ar("'AbtvjHxd*rzs$SDTZEgfqklmnhwy")

sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
sh = sa.open('PACL-Letter-Split')

entries_to_add = pd.read_csv(
    '/Users/chriscay/Downloads/PACL-Letter-Split-Phrase-Lemma-Add.csv')
entries_to_add = entries_to_add.replace(nan, '', regex=True)
assert all(r in valid_radicals_ar for root in entries_to_add['ROOT'] for r in root.split('.'))
 
radical2rows = {}
for i, row in entries_to_add.iterrows():
    row = row.to_dict()
    row['ROOT_NTWS'] = 'NTWS' if row['ROOT STATUS'] == 'NTWS' else ''
    radical2rows.setdefault(row['ROOT'][0], []).append((i, row))

if os.path.exists('added_lemmas.pkl'):
    with open('added_lemmas.pkl', 'rb') as f:
        added_indexes = pickle.load(f)
else:
    added_indexes = set()

pbar = tqdm(total=sum(len(rows) for rows in radical2rows.values()))
restart = False
for first_radical, rows in radical2rows.items():
    pbar.set_description(first_radical)
    sheet = sh.worksheet(first_radical)
    sheet_df = pd.DataFrame(sheet.get_all_records())
    sheet_df = sheet_df.replace(nan, '', regex=True)
    header = sheet.row_values(1)
    for i, row in rows:
        if i in added_indexes:
            pbar.update(1)
            continue
        row['ID'] = 'Auto' if row['LEMMA_AR'].strip() else 'Auto-Shahd'
        row_ = [row.get(h, '').strip() for h in header]
        index = bisect(sheet_df['ROOT'].values.tolist(), row['ROOT'])
        while True:
            try:
                sheet.insert_row(row_, max(2, index - 1))
                break
            except gspread.exceptions.APIError as e:
                if 'Quota exceeded' in e.args[0]['message']:
                    wait = 90
                    print(f'Quota exceeded, waiting for {wait} seconds and then retrying...')
                    time.sleep(wait)
        added_indexes.add(i)
        with open('added_lemmas.pkl', 'wb') as f:
            pickle.dump(added_indexes, f)
        pbar.update(1)
pbar.close()

