import re
import sys
from collections import Counter
from tqdm import tqdm
import random
random.seed(42)

import pandas as pd
from numpy import nan
import gspread

from camel_tools.morphology.utils import strip_lex
from camel_tools.utils.charmap import CharMapper
from camel_tools.morphology.database import MorphologyDB

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

RE_LEX = re.compile(r'lex:([^-_ ]+)(?:-.)?(?:_\d)?|lex:([-_])(?:-.)?(?:_\d)')
RE_POS = re.compile(r'pos:(\S+)')

sys.path.insert(0, '/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/palestinian_lexicon')
import utils

# import gspread

# sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
# sh = sa.open('PACL-Letter-Split')

# madar = pd.read_csv('data/madar-jerusalem.csv')

# sum([True if any([row['الكلمة المقابلة بالفصحى'].strip(),
#                   row['مثال الاستخدام'].strip(),
#                   row['ملاحظات'].strip(),
#                   row['Source'].strip()]) else False
#         for _, row in pacl.iterrows()]) / len(pacl.index)

# root2lexpos = {}
# for _, entries in db.lemma_hash.items():
#     for entry in entries:
#         if 'root' in entry and entry['root'] != 'NTWS':
#             root2lexpos.setdefault(entry['root'], set()).add((entry['lex'].strip(), entry['pos']))

def _preprocess_magold_data(gold_data):
    # List of sentences
    gold_data = gold_data.split('--------------\nSENTENCE BREAK\n--------------\n')[:-1]
    # List of words
    gold_data = sum([sent.split('\n--------------\n')[1:] for sent in tqdm(gold_data, desc='List of words')], [])
    # List of word analyses
    gold_data = [line for word in tqdm(gold_data, desc='List of word analyses')
                      for line in word.strip().split('\n') if line.startswith('*')]
    
    gold_data_ = []
    for analysis in tqdm(gold_data, desc='List of lex:POS'):
        lemma = [grp for grp in RE_LEX.search(analysis).groups() if grp is not None]
        assert len(lemma) == 1
        lemma = lemma[0]
        pos = RE_POS.search(analysis).group(1)

        gold_data_.append([lemma, pos])

    return gold_data_


def preprocessing(lemma):
    lemma = re.sub('o', '', lemma)
    lemma = re.sub('aA', 'A', lemma)
    lemma = re.sub('[ai]p', 'p', lemma)
    lemma = re.sub('{', 'A', lemma)
    return lemma


def perform_eval(lexicon_ref,
                 lexpostype_uniq_pacl,
                 lexpostype_dediac_uniq_pacl,
                 output_name,
                 sample_size,
                 lexpostype2tag=None):
    lexpos_ref = [(preprocessing(strip_lex(l).strip()), pos.strip())
                    for l, pos in lexicon_ref[['Lemma', 'POS']].values.tolist()]
    lexpos2count_ref = Counter(lexpos_ref)

    ref_lexpostype_noun_prop = [(*lexpos, utils.lexpos2lexpostype(lexpos)[1], count)
                                    for lexpos, count in lexpos2count_ref.items() if lexpos[1] == 'noun_prop']
    ref_lexpostype_punc_digit = [(*lexpos, utils.lexpos2lexpostype(lexpos)[1], count)
                                    for lexpos, count in lexpos2count_ref.items() if lexpos[1] in ['punc', 'digit']]

    ref_lexpostype_in_pacl = [
        (*lexpos, utils.lexpos2lexpostype(lexpos)[1], count) for lexpos, count in lexpos2count_ref.items()
        if lexpos[1] not in ['punc', 'digit', 'noun_prop'] and utils.lexpos2lexpostype(lexpos) in lexpostype_uniq_pacl]

    ref_lexpostype_not_in_pacl = [
        (*lexpos, utils.lexpos2lexpostype(lexpos)[1], count) for lexpos, count in lexpos2count_ref.items()
        if lexpos[1] not in ['punc', 'digit', 'noun_prop'] and utils.lexpos2lexpostype(lexpos) not in lexpostype_uniq_pacl]

    # Sanity check
    number_noun_prop = sum(count for _, _, _, count in ref_lexpostype_noun_prop)
    number_punc_digit = sum(count for _, _, _, count in ref_lexpostype_punc_digit)
    number_in_pacl = sum(count for _, _, _, count in ref_lexpostype_in_pacl)
    number_not_in_pacl = sum(count for _, _, _, count in ref_lexpostype_not_in_pacl)
    total = number_noun_prop + number_punc_digit + number_in_pacl + number_not_in_pacl

    randomized = [1]*int(len(ref_lexpostype_not_in_pacl)*sample_size) + [0]*int(len(ref_lexpostype_not_in_pacl)*(1 - sample_size))
    if len(randomized) < len(ref_lexpostype_not_in_pacl):
        randomized += [0] * (len(ref_lexpostype_not_in_pacl) - len(randomized))
    elif len(randomized) > len(ref_lexpostype_not_in_pacl):
        randomized = randomized[:-len(randomized) + len(ref_lexpostype_not_in_pacl)]

    random.shuffle(randomized)
    with open(output_name, 'w') as f:
        print('Index', 'Preprocessed lemma', 'Preprocessed lemma_ar', 'Dediac lexpostype exists in PACL', 'pos', 'postype',
              'Freq', 'Random selection (10\% of FALSE)', 'lexpostype exists in PACL', 'Bank Lookup based on lexpostype', 
              'New annotations -- SHAHD ADD HERE', sep='\t', file=f)
        i = 1
        for lemma, pos, postype, count in ref_lexpostype_in_pacl:
            dediac_in_pacl = (re.sub(r'[aoiu]', '', lemma), postype) in lexpostype_dediac_uniq_pacl
            print(i, lemma, bw2ar(lemma), dediac_in_pacl, pos, postype, count, 0, 'TRUE', 'N/A', '', sep='\t', file=f)
            i += 1
        for r, (lemma, pos, postype, count) in zip(randomized, sorted(ref_lexpostype_not_in_pacl)):
            dediac_in_pacl = (re.sub(r'[aoiu]', '', lemma), postype) in lexpostype_dediac_uniq_pacl
            print(i, lemma, bw2ar(lemma), dediac_in_pacl, pos, postype, count, r, 'FALSE',
                    lexpostype2tag.get((lemma, postype), 'NOT FOUND') if lexpostype2tag is not None else 'N/A', '', sep='\t', file=f)
            i += 1
        for data in [ref_lexpostype_noun_prop, ref_lexpostype_punc_digit]:
            for lemma, pos, postype, count in data:
                print(i, lemma, bw2ar(lemma), 'IGNORE', pos, postype, count, 0, 'IGNORE', 'N/A', '', sep='\t', file=f)
                i += 1

if __name__ == "__main__":
    sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
    sh = sa.open('Maknuune-Release-Camera-Ready')
    sheet = sh.worksheet('Maknuune-v1.0')
    pacl = pd.DataFrame(sheet.get_all_records()).astype(str)
    pacl_obj = pacl.select_dtypes(['object'])
    pacl[pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
    pacl = pacl.replace(nan, '', regex=True)
    
    lexpostype_pacl = [utils.lexpos2lexpostype((preprocessing(ar2bw(l)).strip(), pos.split(':')[0].strip()))
                            for l, pos in pacl[['LEMMA', 'ANALYSIS']].values.tolist()]
    lexpostype_uniq_pacl = set(lexpostype_pacl)
    lexpostype_dediac_uniq_pacl = set([(re.sub(r'[aoiu]', '', lemma), postype) for lemma, postype in lexpostype_pacl])

    # Curras Eval
    curras = pd.read_csv('data/curras-16-04-22.csv')
    # bank = pd.read_csv('eval_bank.csv')
    # lexpostype2tag = {(preprocessing(l).strip(), postype.strip()): tag
    #                 for l, postype, tag in bank[['Curras LEX', 'Curras POS type', "LEX' Exists in PACL"]].values.tolist()}
    perform_eval(curras, lexpostype_uniq_pacl, lexpostype_dediac_uniq_pacl, 'evaluation_sheet_curras_corpus.tsv', 0.1)

    # MSA Lex Eval
    db_msa = MorphologyDB('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/calima-msa-s31_0.4.2.utf8.db', flags='g')
    msa_lex = pd.DataFrame([[ar2bw(a['lex']), a['pos']] for analyses in db_msa.lemma_hash.values() for a in analyses], columns=['Lemma', 'POS'])
    perform_eval(msa_lex, lexpostype_uniq_pacl, lexpostype_dediac_uniq_pacl, 'evaluation_sheet_msa_lex.tsv', 0.02)

    # EGY Lex Eval
    db_egy = MorphologyDB('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/calima-egy-c044_0.2.0.utf8.db', flags='g')
    egy_lex = pd.DataFrame([[ar2bw(a['lex']), a['pos']] for analyses in db_egy.lemma_hash.values() for a in analyses if a['gloss'].endswith('_[CALIMA]')],
                           columns=['Lemma', 'POS'])
    perform_eval(egy_lex, lexpostype_uniq_pacl, lexpostype_dediac_uniq_pacl, 'evaluation_sheet_egy_lex.tsv', 0.02)

    # MSA Corpus Eval
    with open('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/ATB123-train.102312.calima-msa-s31_0.3.0.magold') as f:
        msa_corpus = f.read()
    msa_corpus = _preprocess_magold_data(msa_corpus)
    msa_corpus = pd.DataFrame(msa_corpus, columns=['Lemma', 'POS'])
    perform_eval(msa_corpus, lexpostype_uniq_pacl, lexpostype_dediac_uniq_pacl, 'evaluation_sheet_msa_corpus.tsv', 0.02)

    # EGY Corpus Eval
    with open('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/ARZ-All-train.113012.magold') as f:
        egy_corpus = f.read()
    egy_corpus = _preprocess_magold_data(egy_corpus)
    egy_corpus = pd.DataFrame(egy_corpus, columns=['Lemma', 'POS'])
    perform_eval(egy_corpus, lexpostype_uniq_pacl, lexpostype_dediac_uniq_pacl, 'evaluation_sheet_egy_corpus.tsv', 0.02)




# pos2lemmas_curras_uniq = utils.get_postype2lemma2pos(lexpos_curras)
# lemmas_curras_uniq = set([l for lemmas in pos2lemmas_curras_uniq.values() for l in lemmas])
# lemmas_curras_dediac = set([re.sub(r'\{', 'A', re.sub(r'[aoiu]', '', l)) for l in lemmas_curras_uniq])

# lexpos2pos_pacl = [(ar2bw(l).strip(), pos.split(':')[0].strip())
#                     for l, pos in pacl[['LEMMA', 'ANALYSIS']].values.tolist()]
# pos2lemmas_pacl_uniq = utils.get_postype2lemma2pos(lexpos2pos_pacl)
# lemmas_pacl_uniq = set([l for lemmas in pos2lemmas_pacl_uniq.values() for l in lemmas])
# lemmas_pacl_dediac = set([re.sub(r'\{', 'A', re.sub(r'[aoiu]', '', l)) for l in lemmas_pacl_uniq])

# with open('pacl_eval.tsv', 'w') as f:
#     for pos, lemmas_pacl_uniq in pos2lemmas_pacl_uniq.items():
#         for lemma in lemmas_pacl_uniq:
#             print(bw2ar(lemma), lemma, pos, sep='\t', file=f)

# lemmas_msa = [ar2bw(l) for l in list(db.lemma_hash.keys())]
# lemmas_msa_dediac = [re.sub(r'[aoiu]', '', l) for l in lemmas_msa]

# postype2lexpos = get_postype2lexpos(lemmas_pacl)
