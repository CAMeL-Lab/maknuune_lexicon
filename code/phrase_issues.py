import re
from bisect import bisect
from tqdm import tqdm
import time
import pickle
from collections import Counter

import pandas as pd
from numpy import nan
import gspread

from camel_tools.utils.charmap import CharMapper

import utils

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

valid_radicals_ar = bw2ar("'AbtvjHxd*rzs$SDTZEgfqklmnhwy")

pacl = utils.read_pacl_as_df()

def identify_missing_phrase_lemmas():
    lexposes_pacl = [(ar2bw(l), analysis)
               for l, analysis in pacl[['LEMMA', 'ANALYSIS']].values.tolist()]
    pos2lemmas_pacl_uniq = utils.get_postype2lemma2pos(lexposes_pacl)

    lemmas_pacl_dediac_excl_phrases = set(
        [re.sub(r'\{', 'A', re.sub(r'[aoiu]', '', vv)) for k, v in pos2lemmas_pacl_uniq.items() for vv in v if k != 'phrase'])
    with open('phrase_lemmas_to_add.tsv', 'w') as f:
        lemmas = sorted([x for x in set(pos2lemmas_pacl_uniq['phrase']) - set([vv for k, v in pos2lemmas_pacl_uniq.items() for vv in v if k != 'phrase']) if x])
        for lemma in lemmas:
            lemma_ar = bw2ar(lemma)
            row = pacl[(pacl['LEMMA'] == lemma_ar) & (pacl['ANALYSIS'] == 'PHRASE')]
            row = row.to_dict()
            root, phrases = set(row['ROOT'].values()), set(row['FORM'].values())
            assert len(root) == 1
            root, phrases = list(root)[0], ' *** '.join(phrases)
            lemma_dediac = re.sub(r'\{', 'A', re.sub(r'[aoiu]', '', lemma))
            print(lemma_ar, lemma, bw2ar(lemma_dediac), lemma_dediac in lemmas_pacl_dediac_excl_phrases, phrases, root, sep='\t', file=f)


def add_pos_to_phrase_lemmas_annot():
    lemma2infos = {}
    for _, row in pacl.iterrows():
        pos = row['ANALYSIS'].split(':')[0]
        if pos == 'PHRASE':
            lemma = row['LEMMA']
            lemmas_same = pacl[(pacl['LEMMA'] == lemma) & (pacl['ANALYSIS'] != 'PHRASE')]
            # assert len(lemmas_same.index) != 0
            associated_pos = [x.split(':')[0] for x in lemmas_same['ANALYSIS'].values.tolist() if x != 'PHRASE']
            lemma2infos.setdefault((lemma, row['ROOT']), []).append(
                {'pos': associated_pos, 'phrase': row['FORM']})
    
    lemma2info = {lemma: {'pos': set(sum([info['pos'] for info in infos], [])),
                          'root': root,
                          'phrases': ' *** '.join(info['phrase'] for info in infos)}
                    for (lemma, root), infos in lemma2infos.items()}

    with open('add_pos_to_phrase_lemmas.tsv', 'w') as f:
        print('LEMMA', 'ROOT', 'POS_COUNT', 'POS', sep='\t', file=f)
        for lemma, info in lemma2info.items():
            pos = ' '.join(sorted(info['pos']))
            if len(info['pos']) <= 1:
                print(lemma, info['root'], len(info['pos']), pos, info['phrases'], sep='\t', file=f)
            else:
                for phrase in info['phrases'].split(' *** '):
                    print(lemma, info['root'], len(info['pos']), pos, phrase, sep='\t', file=f)


def add_pos_to_phrase_lemmas_online():
    sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
    sh = sa.open('PACL-Letter-Split')

    entries_to_add = pd.read_csv('/Users/chriscay/Downloads/PACL-Letter-Split - Phrase-Lemma-POS-Annot.csv')
    entries_to_add = entries_to_add.replace(nan, '', regex=True)
    radical2rows = {}
    for i, row in entries_to_add.iterrows():
        radical2rows.setdefault(row['ROOT'][0], []).append((i, row.to_dict()))

    fails = []
    for first_radical, rows in radical2rows.items():
        sheet = sh.worksheet(first_radical)
        sheet_df = pd.DataFrame(sheet.get_all_records())
        assert sheet.row_values(1)[6] == 'ANALYSIS'
        sheet_df = sheet_df.replace(nan, '', regex=True)
        sheet_df_obj = sheet_df.select_dtypes(['object'])
        sheet_df[sheet_df_obj.columns] = sheet_df_obj.apply(lambda x: x.str.strip())
        
        data = []
        for i, row in rows:
            lemma, pos = row['LEMMA'], row['POS']
            phrases = row['PHRASES'].split(' *** ')
            for phrase in phrases:
                matches = sheet_df[(sheet_df['LEMMA'] == lemma) & (sheet_df['FORM'] == phrase)]
                if len(matches.index) != 1:
                    fails.append({'lemma': lemma, 'phrase': phrase, 'root': row['ROOT'], 'pos': pos})
                else:
                    data.append({'range': f'G{matches.index[0] + 2}', 'values': [[f'{pos}:PHRASE']]})
        assert all(sheet_df.iloc[int(d['range'][1:]) - 2]['ANALYSIS'] == 'PHRASE' for d in data)
        sheet.batch_update(data)

# add_pos_to_phrase_lemmas_annot()
identify_missing_phrase_lemmas()
# add_pos_to_phrase_lemmas_online()
pass
