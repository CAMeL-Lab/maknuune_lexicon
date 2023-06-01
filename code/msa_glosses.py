import sys
import re
from collections import Counter

import pandas as pd

sys.path.insert(
    0, "/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_tools")

from camel_tools.morphology.database import MorphologyDB
# from camel_tools.utils.dediac import dediac_ar
from camel_tools.utils.charmap import CharMapper

AR_DIACRITICS = re.compile(r'[ًٌٍَُِْ]')

def dediac_ar(text):
    return AR_DIACRITICS.sub('', text)

DEFAULT_NORMALIZE_MAP = CharMapper({
    'أ': 'ء',
    'إ': 'ء',
    'ؤ': 'ء',
    'ئ': 'ء'
})

maknuune = pd.read_csv('/Users/chriscay/Downloads/Maknuune-WIP - Maknuune-v1.1.csv')

db_msa = MorphologyDB('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/calima-msa-s31_0.4.2.utf8.db', flags='g')
lemma2analyses_msa = db_msa.lemma_hash

def _preprocess_lemma(lemma):
    lemma = dediac_ar(lemma)
    lemma = DEFAULT_NORMALIZE_MAP(lemma)
    return lemma


preprocess2lemmas_msa = {}
for lemma, analyses in lemma2analyses_msa.items():
    for analysis in analyses:
        pos = analysis['pos']
        preprocess2lemmas_msa.setdefault(
            (_preprocess_lemma(lemma), pos), {}).setdefault(
                lemma, set()).add(analysis['gloss'])

rows = {}
lemma_gloss_used = set()
for _, row in maknuune.iterrows():
    if 'PHRASE' in row['ANALYSIS']:
        continue
    lemma = row['LEMMA']
    gloss = row['GLOSS'].replace('_[auto]', '')
    lemma_gloss = (lemma, gloss)
    if lemma_gloss in lemma_gloss_used:
        continue
    lemma_gloss_used.add(lemma_gloss)
    gloss_msa = row['GLOSS_MSA']
    entry_id = row['ID']
    pos = row['ANALYSIS'].split(':')[0].lower()
    lemma_pos_preprocess = (_preprocess_lemma(lemma), pos)
    if lemma_pos_preprocess in preprocess2lemmas_msa: 
        lemmas_calima = preprocess2lemmas_msa[lemma_pos_preprocess]
        for lemma_calima, glosses_calima in lemmas_calima.items():
            gloss_calima = '###'.join(glosses_calima)
            rows.setdefault('POS', []).append(pos)
            rows.setdefault('LEMMA_CALIMA', []).append(lemma_calima)
            rows.setdefault('GLOSS_CALIMA', []).append(gloss_calima)
            rows.setdefault('ID', []).append(entry_id)
            rows.setdefault('GLOSS', []).append(gloss)
            rows.setdefault('LEMMA', []).append(lemma)
            rows.setdefault('GLOSS_MSA', []).append(gloss_msa)
            rows.setdefault('NUM_POSS', []).append(len(lemmas_calima))

with open('msa_glosses.tsv', 'w') as f:
    df = pd.DataFrame(rows)
    df = df[['NUM_POSS', 'ID', 'LEMMA', 'POS', 'GLOSS', 'GLOSS_MSA', 'LEMMA_CALIMA', 'GLOSS_CALIMA']]
    df.to_csv(f, '\t')


pass