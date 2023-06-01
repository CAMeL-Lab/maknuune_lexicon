import re
from collections import Counter

from camel_tools.utils.charmap import CharMapper

import utils
from utils_old import AlignmentHandler
from well_formedness import get_caphi_symbols_inventory

from nltk import AlignedSent, IBMModel4
from edit_distance import SequenceMatcher

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

pacl = utils.read_pacl_as_df()
caphi_inventory, _ = get_caphi_symbols_inventory()

# counts = {}
# for _, row in pacl.iterrows():
#     caphi = row['CAPHI++'].replace('II', '||')
#     counts.setdefault(caphi.count('||'), []).append(caphi)

def _expand_caphi(caphi_split):
    expansions = [[]]
    for c in caphi_split:
        for expansion in expansions:
            if '||' not in c:
                expansion.append(c)
            else:
                expansions_ = []
                for cc in c.split('||'):
                    expansions_.append(expansions[-1][:] + [cc])
                expansions = expansions_
    return expansions


def get_caphi(caphi):
    expansions = []
    for caphi_ in caphi.split(','):
        caphi_ = caphi_.strip()
        caphi_split = caphi_.split()
        if '#' in caphi_ or sum('||' in c for c in caphi_split) > 1:
            discarded.append((form, caphi_))
            continue
        
        expansions_ = [caphi_split]
        if '||' in caphi_:
            expansions_ = _expand_caphi(caphi_split)

        if not all(c in caphi_inventory for caphi_split in expansions_ for c in caphi_split):
            discarded.append((form, caphi_))
            continue

        expansions += expansions_
    
    return expansions


def _preprocess(text):
    text = text.replace('o', '')
    text = text.replace('aA', 'A')
    text = re.sub(r'[aiuo]$', '', text)
    text = re.sub(r'{', 'A', text)
    return text


bitext = []
discarded = []
sequences = {}
for _, row in pacl.iterrows():
    form, caphi = row['FORM'], row['CAPHI++']
    caphi = row['CAPHI++'].replace('II', '||')
    caphi = get_caphi(caphi)
    for caphi_ in caphi:
        # bitext.append(AlignedSent(caphi_, list(ar2bw(form))))
        form_bw = _preprocess(ar2bw(form))
        seq1, seq2 = AlignmentHandler.align([[c, 'n'] for c in list(form_bw)], [[c, 'n'] for c in caphi_])
        seq1, seq2 = AlignmentHandler.align_subsequences(seq1, seq2)

        # sequences_ = []
        # for i in range(len(src)):
        #     if src[i][1] in 'id':
        #         sequences_.append((src[i][0], 'inserted' if src[i][1] == 'i' else 'deleted'))
        #     elif src[i][1] == 's':
        #         sequences_.append((src[i][0], 'inserted' if src[i][1] == 'i' else 'deleted'))

        # sequence = tuple([(tuple(src[i]), tuple(tgt[i])) for i in range(len(src)) if src[i][1] != 'e'])
        for i in range(len(seq1)):
            if seq1[i][1] == 'ne':
                sequence = (seq1[i][0], seq2[i][0])
                sequences.setdefault(sequence, [0, []])
                sequences[sequence][0] += 1
                sequences[sequence][1].append((form_bw, ''.join(caphi_)))

# ibm = IBMModel3(bitext[:100], 5)

pass