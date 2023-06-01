import re

import pandas as pd
from numpy import nan

CAPHI_DELIM_RE = re.compile(r'[,#]')


def get_sub_ipa(caphi_sub):
    return ''.join(caphi2ipa.get(c, '\\#') for c in caphi_sub)

def caphipp2ipa(caphipp):
    assert not (',' in caphipp and '#' in caphipp)
    ipa = []
    for caphi_sub in CAPHI_DELIM_RE.split(caphipp):
        ipa.append([])
        caphi_sub = caphi_sub.strip().split()
        ored_char_indexes = [i for i, c in enumerate(caphi_sub) if '||' in c]
        if len(ored_char_indexes) >= 1:
            if len(set([caphi_sub[i] for i in ored_char_indexes])) == 1:
                pass
            else:
                raise NotImplementedError
        if ored_char_indexes:
            caphi_subs = []
            for c in caphi_sub[ored_char_indexes[0]].split('||'):
                caphi_subs.append(get_sub_ipa(
                    ''.join(
                        ''.join(caphi_sub[(ored_char_indexes[i - 1] if i > 0 else 0):or_index] + [c] +
                                caphi_sub[or_index + 1: (ored_char_indexes[i + 1] if i + 1 < len(ored_char_indexes) else 100)])
                        for i, or_index in enumerate(ored_char_indexes))))
            ipa[-1] = ', '.join(caphi_subs)
        else:
            ipa[-1] = get_sub_ipa(caphi_sub)
    ipa = f"{', ' if ',' in caphipp else ' '}".join(ipa)
    
    return ''.join(ipa)


if __name__ == "__main__":
    caphi_inventory = pd.read_csv('caphi_table_full.tsv', sep='\t')
    caphi2ipa = {}
    for _, row in caphi_inventory.iterrows():
        caphi2ipa[row['CAPHI']] = row['IPA']
    
    CAPHI_SPECIAL_CHARS_MAP = {
        'Q': {'caphi':['q', 'k', '2', 'g'], 'tipa++': '(q)', 'ipa': '(q)'},
        'D': {'caphi':['dh', 'd'], 'tipa++': '(d)', 'ipa': '(d)'},
        'J': {'caphi':['j', 'dj'], 'tipa++': '(\\t{dZ})', 'ipa': f"({caphi2ipa['dj']})"},
        'Z': {'caphi':['z', 'dh'], 'tipa++': '(D)', 'ipa': f"({caphi2ipa['dh']})"},
        'T': {'caphi':['t', 'th'], 'tipa++': '(t)', 'ipa': '(t)'},
        'S': {'caphi':['s', 'th'], 'tipa++': '(T)', 'ipa': f"({caphi2ipa['th']})"},
        'Z.': {'caphi':['z.', 'dh.'], 'tipa++': '(D\\super Q)', 'ipa': f"({caphi2ipa['dh.']})"},
        'D.': {'caphi':['d.', 'dh.'], 'tipa++': '(d\\super Q)', 'ipa': f"({caphi2ipa['d.']})"},
        'K': {'caphi':['k', 'tsh'], 'tipa++': '(k)', 'ipa': '(k)'}
    }
    caphi2ipa = {**caphi2ipa, **{k: v['ipa'] for k, v in CAPHI_SPECIAL_CHARS_MAP.items()}}

    path = ...
    sheet = pd.read_csv(path, sep='\t')
    pacl = pd.DataFrame(sheet).astype(str)
    pacl_obj = pacl.select_dtypes(['object'])
    pacl[pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
    pacl = pacl.replace(nan, '', regex=True)
    pacl['CAPHI++'] = pacl.apply(lambda row: re.sub(r'II', '||', row['CAPHI++']), axis=1)
    pacl = pacl.replace('\"', '', regex=True)
    pacl = pacl.replace('%', '\\%', regex=True)

    for _, row in pacl.iterrows():
        caphipp = row['CAPHI++']
        ipa = caphipp2ipa(caphipp)