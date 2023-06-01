import os
import re
from collections import Counter
import time

from camel_tools.utils.charmap import CharMapper

import gspread
import pandas as pd
from numpy import nan

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

sheet_names = ['ء', 'ب', 'ت', 'ث', 'ج', 'ح', 'خ', 'د', 'ذ', 'ر', 'ز', 'س', 'ش', 'ص',
               'ض', 'ط', 'ظ', 'ع', 'غ', 'ف', 'ق', 'ك', 'ل', 'م', 'ن', 'ه', 'و', 'ي']

def add_check_mark_online(rows,
                          spreadsheet,
                          sheet,
                          error_cases=None,
                          indexes=None,
                          messages=None,
                          mode=None,
                          write='append',
                          status_col_name='STATUS',
                          service_account='/Users/chriscay/.config/gspread/service_account.json'):
    assert bool(error_cases) ^ bool(indexes) ^ bool(messages)
    if error_cases is not None:
        filtered = rows[rows['LEMMA'].isin(error_cases)]
        indexes = filtered.index

    if type(spreadsheet) is str:
        sa = gspread.service_account(service_account)
        spreadsheet = sa.open(spreadsheet)

    if type(sheet) is str:
        worksheet = spreadsheet.worksheet(title=sheet)
    else:
        worksheet = sheet

    header = worksheet.row_values(1)
    header_count = header.count(status_col_name)
    if header_count == 0:
        worksheet.insert_cols([[status_col_name]])
        header = worksheet.row_values(1)
    elif header_count > 1:
        raise NotImplementedError

    status_column_index = header.index(status_col_name)
    column_letter = (chr(ord('A') + status_column_index // 27) if status_column_index >= 26 else '') + \
        chr(ord('A') + status_column_index % 26)

    status_old = worksheet.col_values(status_column_index + 1)[1:]
    lemmas = worksheet.col_values(header.index('LEMMA') + 1)[1:]
    status_old += [''] * (len(lemmas) - len(status_old))
    assert len(lemmas) == len(status_old) == len(rows['LEMMA'])
    col_range = f'{column_letter}2:{len(rows.index) + 1}'

    if indexes:
        if mode:
            check, ok = f'{mode}:CHECK', f'{mode}:OK'
        else:
            check, ok = 'CHECK', 'OK'
        assert set(status_old) <= {check, ok, ''}
        status_new = [[check] if i in indexes else ([ok] if status_old[i] != check else [check])
                      for i in range(len(rows['LEMMA']))]
    elif messages:
        assert len(status_old) == len(lemmas) == len(messages)
        if write == 'overwrite':
            status_new = [[f'{message}'] if message else ['']
                          for message in messages]
        elif write == 'append':
            status_new = [[f"{s}{' ' if s else ''}" + f'{message}'] if message else [s + '']
                          for s, message in zip(status_old, messages)]
    else:
        raise NotImplementedError

    worksheet.update(col_range, status_new)


def read_pacl_as_df(directory='data/letter_split', sheet_names=sheet_names):
    pacl = pd.DataFrame([])
    for sheet_name in sheet_names:
        path = os.path.join(directory, f'{sheet_name}.csv')
        sheet_lines_, rewrite = [], False
        with open(path) as f:
            for i, line in enumerate(f.readlines()):
                if re.match(r'\d+', line) or i == 0:
                    sheet_lines_.append(line.strip())
                else:
                    rewrite = True
                    status_column_index = line.count(',') - 1
                    col_letter = (chr(ord('A') + status_column_index // 27) if status_column_index >= 26 else '') + \
                                  chr(ord('A') + status_column_index % 26)
                    print(f'WARNING: New line in sheet <{sheet_name}>, cell {col_letter}{i}')
                    sheet_lines_[-1] += line.strip()
        
        if rewrite:
            with open(path, 'w') as f:
                for line in sheet_lines_:
                    print(line, file=f)

        pacl = pd.concat([pacl, pd.read_csv(path)], ignore_index=True)
    
    pacl_obj = pacl.select_dtypes(['object'])
    pacl[pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
    pacl = pacl.replace(nan, '')
    return pacl

def read_pacl_as_dfs(directory='data/letter_split', sheet_names=sheet_names):
    pacl = {}
    for sheet_name in sheet_names:
        pacl[sheet_name] = pd.read_csv(os.path.join(directory, f'{sheet_name}.csv'))
        pacl[sheet_name] = pacl[sheet_name].replace(nan, '')
        pacl_obj = pacl[sheet_name].select_dtypes(['object'])
        pacl[sheet_name][pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
    return pacl


def lexpos2lexpostype(lexpos):
    pos = lexpos[1].lower()
    if pos in {'noun', 'adj', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant'}:
        return (lexpos[0], 'nom')
    elif pos == 'verb':
        return (lexpos[0], 'verb')
    elif pos in {'noun_prop', 'foreign'}:
        return (lexpos[0], 'noun_prop-foreign')
    else:
        return (lexpos[0], 'other')

        
def get_postype2lemma2pos(lemmas):
    pos2lemmas_uniq = {'phrase': {}, 'nom': {}, 'verb': {},
                       'noun_prop-foreign': {}, 'other': {}}
    for l, analysis in lemmas:
        analysis = analysis.split(':')
        if len(analysis) == 2:
            pos, feats = analysis
        else:
            pos, feats = analysis[0], ''
        pos, feats = pos.lower(), feats.lower()
        if feats == 'phrase':
            pos2lemmas_uniq[feats].setdefault(l, set()).add(feats)
        elif pos in {'noun', 'adj', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant'}:
            pos2lemmas_uniq['nom'].setdefault(l, set()).add(pos)
        elif pos == 'verb' and feats !=' phrase':
            pos2lemmas_uniq[pos].setdefault(l, set()).add(pos)
        elif pos in {'noun_prop', 'foreign'}:
            pos2lemmas_uniq['noun_prop-foreign'].setdefault(l, set()).add(pos)
        else:
            pos2lemmas_uniq['other'].setdefault(l, set()).add(pos)
    return pos2lemmas_uniq


def get_postype2pos2lemmas(lemmas):
    postype2pos2lemmas = {'phrase': {}, 'nom': {}, 'verb': {},
                          'noun_prop-foreign': {}, 'other': {}}
    for l, pos in lemmas:
        pos = pos.lower()
        if pos in {'noun', 'noun_num', 'adj', 'adj_num', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant', 'adv', 'verb_nom', 'adv_rel'}:
            postype2pos2lemmas['nom'].setdefault(pos, []).append(l)
        elif pos in {'verb', 'phrase'}:
            postype2pos2lemmas[pos].setdefault(pos, []).append(l)
        elif pos in {'noun_prop', 'foreign'}:
            postype2pos2lemmas['noun_prop-foreign'].setdefault(
                pos, []).append(l)
        else:
            postype2pos2lemmas['other'].setdefault(pos, []).append(l)
    return postype2pos2lemmas


def get_postype2lexpos(lemmas):
    postype2lexpos = {'nom': Counter(), 'verb': Counter(),
                      'noun_prop-foreign': Counter(), 'other': Counter()}
    for l, pos in lemmas:
        pos = pos.lower()
        lexpos = (l, pos)
        if pos in {'noun', 'adj', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant'}:
            postype2lexpos['nom'].update([lexpos])
        elif pos in {'verb', 'phrase'}:
            postype2lexpos[pos].update([lexpos])
        elif pos in {'noun_prop', 'foreign'}:
            postype2lexpos['noun_prop-foreign'].update([lexpos])
        else:
            postype2lexpos['other'].update([lexpos])
    return postype2lexpos


def preprocessing_pacl(pacl):
    regex1 = f"{bw2ar('o')}|"
    pacl['LEMMA'] = pacl.apply(lambda row: re.sub(r'', '', row['LEMMA']))


def index2letter(index):
    return (chr(ord('A') + index // 27) if index >= 26 else '') + chr(ord('A') + index % 26)


def try_google_api_until_succeded(func, *args):
    while True:
        try:
            func(*args)
            break
        except gspread.exceptions.APIError as e:
            if 'Quota exceeded' in e.args[0]['message']:
                wait = 90
                print(f'Quota exceeded, waiting for {wait} seconds and then retrying...')
                time.sleep(wait)