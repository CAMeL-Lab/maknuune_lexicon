import pandas as pd
from collections import Counter
from bisect import bisect
from tqdm import tqdm

from numpy import nan
from scipy import spatial
from nltk.metrics.distance import edit_distance
import gspread

import utils

maknuune_wip = pd.read_csv('/Users/chriscay/Downloads/Maknuune-WIP - Maknuune-v1.1 (2).csv')
maknuune_wip = maknuune_wip.replace(nan, '')
maknuune_release = pd.read_csv('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/palestinian_lexicon/data_release/maknuune-v1.0.2/maknuune-v1.0.2.tsv', sep='\t')
maknuune_release = maknuune_release.replace(nan, '')

diff_qc = pd.read_csv('/Users/chriscay/Downloads/Maknuune-WIP - Diff-Release-WIP.csv')

header = ['ROOT', 'LEMMA', 'FORM', 'CAPHI++', 'ANALYSIS']
header_1 = [f'{h}.1' for h in header]
maknuune_release_set = Counter(tuple(row) for row in maknuune_release[header].values.tolist())
maknuune_wip_set = Counter(tuple(row) for row in maknuune_wip[header].values.tolist())

confounded_release = {k for k, v in maknuune_release_set.items() if v > 1}
confounded_wip = {k for k, v in maknuune_wip_set.items() if v > 1}
confounded_union = confounded_release | confounded_wip

edits_ok = set(tuple(row) for row in diff_qc[diff_qc['QC'] == 'OK'][header_1].replace(
            r'[][]', '', regex=True).values.tolist())
edits_prob = set(tuple(row) for row in diff_qc[diff_qc['QC'] == 'PROB'][header_1].replace(
            r'[][]', '', regex=True).values.tolist())
deletes = set(tuple(row) for row in diff_qc[diff_qc['QC'] == 'DELETED'][header_1].replace(
            r'[][]', '', regex=True).values.tolist())
no_match = set(tuple(row) for row in diff_qc[diff_qc['QC'] == 'NO-MATCH'][header_1].replace(
            r'[][]', '', regex=True).values.tolist())

added_entries = set()
for k in set(maknuune_wip_set) - set(maknuune_release_set):
    if k not in edits_ok and k not in edits_prob and k not in deletes:
        added_entries.add(k)

sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
sh = sa.open('Maknuune-WIP')
sheet = sh.worksheet('Maknuune-v1.1')

messages = []
for _, row in maknuune_wip.iterrows():
    k = tuple(row[header].values.tolist())
    if k in added_entries:
        messages.append('insert')
    elif k in edits_ok:
        messages.append('edit_ok')
    elif k in edits_prob:
        messages.append('edit_prob')
    elif k in deletes:
        messages.append('delete')
    elif k in no_match:
        messages.append('no_match')
    else:
        messages.append('')

utils.add_check_mark_online(
    maknuune_wip, sh, sheet, write='overwrite',
    messages=messages, status_col_name='DIFF')


header2order = {}
for i, h in enumerate(header):
    for k in maknuune_wip_set:
        header2order.setdefault(h, set()).add(k[i])
    header2order[h] = sorted(header2order[h])

key2vector_wip = {k: [bisect(header2order[h], k[i]) for i, h in enumerate(header)]
                  for k in maknuune_wip_set}
vector2key_wip = {tuple(v): k for k, v in key2vector_wip.items()}
vectors_wip = list(key2vector_wip.values())
tree = spatial.KDTree(vectors_wip)

old2new, unsorted = {}, {}
for k in tqdm(set(maknuune_release_set) - set(maknuune_wip_set)):
    k_vector = tuple(bisect(header2order[h], k[i]) for i, h in enumerate(header))
    k_news = [vector2key_wip[tuple(vectors_wip[nn])] for nn in tree.query(k_vector, len(vectors_wip))[1]]
    k_news_ = []
    for i_k_new, k_new in enumerate(k_news):
        k_ = []
        for kk_old, kk_new in zip(k, k_new):
            k_.append(f'[{kk_old}]' if kk_old != kk_new else kk_old)
        count = sum(1 for kk in k_ if kk[0] == '[')
        if count <= 2:
            k_news_.append(k_new)
            if len(k_news_) == 1:
                best_distance, best_index = 100000, -1
                for i, k_new_ in enumerate(k_news_):
                    distance = edit_distance(''.join(k_new_), ''.join(k))
                    if distance < best_distance:
                        best_index = i
                        best_distance = distance
                old2new[tuple(k_)] = k_news_[best_index]
                break
    else:
        unsorted[tuple(k_)] = k_new

with open('maknuune_merge/old2new.tsv', 'w') as f:
    print(*header, *header, sep='\t', file=f)
    for old, new in old2new.items():
        print(*old, *new, sep='\t', file=f)
    print(*['']*len(header)*2, sep='\t', file=f)
    for old, new in unsorted.items():
        print(*old, *new, sep='\t', file=f)


pass