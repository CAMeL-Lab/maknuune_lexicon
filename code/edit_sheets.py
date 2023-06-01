import re
from itertools import permutations
from tqdm import tqdm

import pandas as pd
from numpy import nan
import gspread

from camel_tools.utils.charmap import CharMapper

import utils
from well_formedness import diacritics_no_gem_ar, fatHa_ar, kasra_ar, Alif_ar, tanwyn_ar

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

valid_radicals_ar = bw2ar("'AbtvjHxd*rzs$SDTZEgfqklmnhwy")

# sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
# sh = sa.open('PACL-Letter-Split')


def edit_column(col_names, mode=''):
    ambiguous = {}
    for sheet_name in tqdm(utils.sheet_names):
        sheet = sh.worksheet(sheet_name)
        sheet_df = pd.DataFrame(sheet.get_all_records())
        sheet_df_obj = sheet_df.select_dtypes(['object'])
        sheet_df[sheet_df_obj.columns] = sheet_df_obj.apply(lambda x: x.str.strip())
        sheet_df = sheet_df.replace(nan, '', regex=True)
        header = list(sheet_df.columns)
        
        data = []
        for col_name in col_names:
            status_column_index = header.index(col_name)
            col_letter = (chr(ord('A') + status_column_index // 27) if status_column_index >= 26 else '') + \
                chr(ord('A') + status_column_index % 26)
            assert header[status_column_index] == col_name
            if mode == 'empty_entry_cells':
                data += _empty_entry_cells(sheet_df, col_name, col_letter, ambiguous, sheet_name)
            elif mode == 'process_lex_form':
                data += _process_lex_form(sheet_df, col_name, col_letter)
            elif mode == 'remove_spaces_analysis':
                data += _remove_spaces_analysis(sheet_df, col_name, col_letter)
            elif mode == 'caphi_correction':
                data += _caphi_correction(sheet_df, col_name, col_letter)
            else:
                raise NotImplementedError
        
        if data:
            sheet.batch_update(data)
    pass


def add_bw(sheet_name):
    sheet = sh.worksheet(sheet_name)
    sheet_df = pd.DataFrame(sheet.get_all_records())
    sheet_df = sheet_df.replace(nan, '', regex=True)
    header = list(sheet_df.columns)
    columns_bw_insert, columns_bw_update  = [], []
    for col_name in ['FORM', 'LEMMA']:
        col_name_bw = f'{col_name}_BW'
        count = header.count(col_name_bw)
        col_bw = [col_name_bw] + [ar2bw(row) for row in sheet_df[col_name].values.tolist()]
        if count == 0:
            columns_bw_insert.append(col_bw)
        else:
            col_index = header.index(col_name_bw)
            col_letter = (chr(ord('A') + col_index // 27) if col_index >= 26 else '') + \
                chr(ord('A') + col_index % 26)
            assert header[col_index] == col_name_bw
            columns_bw_update.append({'range': f'{col_letter}2:{col_letter}{len(sheet_df.index) + 1}',
                                        'values': [[c] for c in col_bw[1:]]})

    
    if columns_bw_insert:
        sheet.insert_cols(columns_bw_insert, col=header.index('FORM') + 2)
    if columns_bw_update:
        sheet.batch_update(columns_bw_update)


def _empty_entry_cells(sheet_df, col_name, col_letter, ambiguous, sheet_name):
    data = []
    for i, row in sheet_df.iterrows():
        if not row[col_name].strip():
            matches = sheet_df[sheet_df['LEMMA'] == row['LEMMA']]
            matches_ = []
            for _, match in matches.iterrows():
                if match[col_name].strip() and match['ANALYSIS'] != 'PHRASE' and match['ANALYSIS'].split(':')[0] == row['ANALYSIS'].split(':')[0]:
                    matches_.append(match)
            if len(matches_) == 1 or len(matches_) > 1 and \
                    any(all(matches_[p[0]][col_name] in matches_[pp][col_name] for pp in p[1:]) for p in permutations(range(len(matches_)))):
                data.append({'range': f'{col_letter}{i + 2}',
                                'values': [[f"{matches_[0][col_name]}_[auto]"]]})
            else:
                ambiguous.setdefault(sheet_name, []).append(row)
    assert all(sheet_df.iloc[int(d['range'][1:]) - 2][col_name].strip() == '' for d in data)
    return data


def _process_lex_form(sheet_df, col_name, col_letter):
    data = []
    for i, row in sheet_df.iterrows():
        cell = re.sub(r'َا', 'ا', row[col_name]).strip()
        cell = re.sub(f'[{diacritics_no_gem_ar}]($| )', r'\1', cell)
        cell = re.sub(f'(?<!^){fatHa_ar}?{Alif_ar}(?!{tanwyn_ar})', f'{fatHa_ar}{Alif_ar}', cell)
        cell = re.sub(f' +{fatHa_ar}', ' ', cell)
        cell = re.sub(f'{tanwyn_ar}{fatHa_ar}{Alif_ar}', f'{Alif_ar}{tanwyn_ar}', cell)
        cell = re.sub(f'إ{kasra_ar}?', f'إ{kasra_ar}', cell)
        if cell != row[col_name]:
            data.append({'range': f'{col_letter}{i + 2}', 'values': [[cell]]})
    return data

def _remove_spaces_analysis(sheet_df, col_name, col_letter):
    data = []
    for i, row in sheet_df.iterrows():
        cell = re.sub(' ', '', row[col_name])
        data.append({'range': f'{col_letter}{i + 2}', 'values': [[cell]]})
    return data

def _caphi_correction(sheet_df, col_name, col_letter):
    data = []
    for i, row in sheet_df.iterrows():
        cell = re.sub('II', '||', row[col_name])
        cell = re.sub(r' *, *', ' , ', cell).strip()
        if cell != row[col_name]:
            data.append({'range': f'{col_letter}{i + 2}', 'values': [[cell]]})
    return data

# pacl = utils.read_pacl_as_df()
sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
# sh = sa.open('PACL-Letter-Split')
# sheet_names = utils.sheet_names
sh = sa.open('Maknuune-Release-Camera-Ready')
sheet_names = ['Maknuune-v1.0']

# edit_column(col_names=['LEMMA', 'FORM', 'مثال الاستخدام', 'الكلمة المقابلة بالفصحى'], mode='process_lex_form')
# edit_column(col_names=['CAPHI++'], mode='caphi_correction')

for sheet_name in tqdm(sheet_names):
    add_bw(sheet_name)
