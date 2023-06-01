from camel_tools.morphology.utils import strip_lex
from camel_tools.utils.charmap import CharMapper

import pandas as pd
from numpy import nan
import gspread

import utils

sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")

# db = MorphologyDB('/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/eval_files/calima-msa-s31_0.4.2.utf8.db', flags='g')

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

LEXPOS1 = set()



def generate_lexicon_curras(curras):
    curras_lexicon = set()
    for _, row in curras.iterrows():
        lemma = strip_lex(row['Lemma'])
        form = row['CODA_Surface']
        analysis = f"{row['POS']}:{''.join(f for f in [row['Person'], row['Gender'], row['Number'], row['Aspect']] if f != 'na')}".upper()
        curras_lexicon.add((lemma, form, analysis))
    
    curras_lexicon_df = pd.DataFrame([list(entry) for entry in curras_lexicon])
    curras_lexicon_df.columns = ['LEMMA', 'FORM', 'ANALYSIS']
    return curras_lexicon_df


def pos_dist1(pacl, curras):
    def pos_dist1_dataset(lemmas):
        postype2pos2lemma = utils.get_postype2pos2lemmas(lemmas)
        postype2lexpos_counts = {
            pos_type: {pos: (len(lemmas), len(set(lemmas))) for pos, lemmas in poses.items()}
            for pos_type, poses in postype2pos2lemma.items()}

        statistics = []
        for pos_type, pos2counts in postype2lexpos_counts.items():
            for pos, counts in pos2counts.items():
                statistics.append([pos_type, pos, *counts])
    
        return statistics

    lemmas_curras = [(strip_lex(l), pos) for l, pos in curras[['Lemma', 'POS']].values.tolist()]
    lemmas_pacl = [(ar2bw(l), pos.split(':')[0].strip()) for l, pos in pacl[['LEMMA', 'ANALYSIS']].values.tolist()]
    
    sheet = sh.worksheet('Stats-POS-Dist-1')
    row_1, row_2 = sheet.row_values(1), sheet.row_values(2)
    assert row_1[0] == 'Maknuune' and row_1[7] == 'Curras'
    assert row_2[:13] == ['POS_TYPE', 'POS', 'COUNT_ENTRIES', '%_ENTRIES', 'COUNT_LEMMAS',
                          '%_LEMMAS', '', 'POS_TYPE', 'POS', 'COUNT_ENTRIES', '%_ENTRIES',
                          'COUNT_LEMMAS', '%_LEMMAS']
    data = []
    ranges = []
    for col, lemmas in [('AF', lemmas_pacl), ('HM', lemmas_curras)]:
        statistics = pos_dist1_dataset(lemmas)
        total_entries = sum(s[2] for s in statistics)
        total_lemmas = sum(s[3] for s in statistics)
        for s in statistics:
            s.insert(3, f'{s[2]/total_entries:.1%}')
            s.append(f'{s[4]/total_lemmas:.1%}')
        statistics.append(['TOTAL', '', total_entries,
                           f'{total_entries/total_entries:.1%}', total_lemmas, f'{total_lemmas/total_lemmas:.1%}'])
        
        ranges.append(len(statistics) + 2)
        data.append({'range': f'{col[0]}3:{col[1]}{max(ranges)}',
                     'values': statistics})
    sheet.batch_update(data)

def pos_dist2(pacl):
    postype2lexpos, postype2form, postype2phrases, postype2entries = {}, {}, {}, {}
    for _, row in pacl.iterrows():
        analysis = row['ANALYSIS'].split(':')
        if len(analysis) == 2:
            pos, feats = analysis
        else:
            pos, feats = analysis[0], ''

        pos = pos.lower()
        if pos in {'noun', 'noun_num', 'adj', 'adj_num', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant', 'adv', 'verb_nom', 'adv_rel'}:
            postype = 'nom'
        elif pos == 'verb':
            postype =  pos
        elif pos in {'noun_prop', 'foreign'}:
            postype = 'noun_prop-foreign'
        else:
            postype = 'other'
        
        if feats == 'PHRASE':
            postype2phrases.setdefault(postype, []).append(row['LEMMA'])
        else:
            postype2form.setdefault(postype, []).append(row['FORM'])
            lexpos = (row['LEMMA'], pos)
            LEXPOS1.add(lexpos)
            postype2lexpos.setdefault(postype, []).append(lexpos)
            postype2entries.setdefault(postype, 0)
        
        postype2entries[postype] += 1
    
    statistics = [['', '# unique lexpos', '# entries', '# forms', '# phrase lemmas']]
    for postype in postype2lexpos:
        statistics.append([postype,
                           len(set(postype2lexpos[postype])),
                           postype2entries[postype],
                           len(postype2form[postype]),
                           len(postype2phrases.get(postype, []))])
    
    sheet = sh.worksheet('Stats-POS-Dist-2')
    sheet.batch_update([{'range': 'A1:E5', 'values': statistics}])
    

def pos_dist3(pacl, curras):
    lexicon_curras = generate_lexicon_curras(curras)

    def get_pos(lexicon):
        return set([analysis.split(':')[0].strip()
                    for analysis in lexicon['ANALYSIS'].values.tolist()])

    def get_lexpos_type(lexicon):
        lexpostypes = set()
        for lemma, analysis in lexicon[['LEMMA', 'ANALYSIS']].values.tolist():
            pos = analysis.split(':')[0].strip().lower()
            if pos in {'noun', 'noun_num', 'adj', 'adj_num', 'noun_act', 'noun_pass', 'adj/noun', 'adj_comp', 'noun_quant', 'adv', 'verb_nom', 'adv_rel'}:
                postype = 'nom'
            elif pos == 'verb':
                postype =  pos
            elif pos in {'noun_prop', 'foreign'}:
                postype = 'noun_prop-foreign'
            else:
                postype = 'other'
            lexpostypes.add((lemma.strip(), postype))
        
        return lexpostypes
    
    def get_pos_features(lexicon):
        return set([tuple([x.strip() for x in analysis.split(':')])
                    for analysis in lexicon['ANALYSIS'].values.tolist() if 'PHRASE' not in analysis])

    def get_lexpos(lexicon):
        return set([(lemma.strip(), analysis.split(':')[0].strip())
                    for lemma, analysis in lexicon[['LEMMA', 'ANALYSIS']].values.tolist()])

    def get_lexpos_features(lexicon):
        return set([(lemma.strip(),) + tuple([x.strip() for x in analysis.split(':')])
                    for lemma, analysis in lexicon[['LEMMA', 'ANALYSIS']].values.tolist()
                    if 'PHRASE' not in analysis])
    
    def get_lexpos_features2forms(lexicon):
        lexpos_features2forms = {}
        for lemma, analysis, form in lexicon[['LEMMA', 'ANALYSIS', 'FORM']].values.tolist():
            if 'PHRASE' not in analysis:
                lexpos_features2forms.setdefault((lemma.strip(),) + tuple([x.strip() for x in analysis.split(':')]), []).append(form.strip())
        return lexpos_features2forms

    # def get_posperlemma(lexicon):
    #     lemma2pos = {}
    #     for _, row in lexicon.iterrows():
    #         lemma2pos.setdefault(row['LEMMA'].strip(), []).append(row['ANALYSIS'].split(':')[0].strip())
        
    #     posperlemma = {}
    #     for lemma, pos in lemma2pos.items():
    #         pos = set(pos)
    #         posperlemma.setdefault(len(pos), []).append((lemma, ' '.join(pos)))
        
    #     return posperlemma
    
    # posperlemma_pacl = get_posperlemma(pacl)
    # posperlemma_curras = get_posperlemma(lexicon_curras)

    # with open('posperlemma_pacl.tsv', 'w') as f:
    #     for number_pos, lemmas in posperlemma_pacl.items():
    #         if number_pos > 1:
    #             for lemma, pos in lemmas:
    #                 print(lemma, pos, number_pos, sep='\t', file=f)

    # with open('posperlemma_curras.tsv', 'w') as f:
    #     for number_pos, lemmas in posperlemma_curras.items():
    #         if number_pos > 1:
    #             for lemma, pos in lemmas:
    #                 print(lemma, pos, number_pos, sep='\t', file=f)

    metrics = []

    entries_curras = list(lexicon_curras.index)
    entries_pacl = list(pacl.index)
    metrics.append(['All entries', entries_curras, entries_pacl])

    lexpos_curras = get_lexpos(lexicon_curras)
    lexpos_pacl = get_lexpos(pacl)
    metrics.append(['Unique lemma:POS', lexpos_curras, lexpos_pacl])

    lexpos_type_curras = get_lexpos_type(lexicon_curras)
    lexpos_type_pacl = get_lexpos_type(pacl)
    metrics.append(['Unique lemma:POSType', lexpos_type_curras, lexpos_type_pacl])

    lemmas_curras = set(lexicon_curras['LEMMA'].values.tolist())
    lemmas_pacl = set(pacl['LEMMA'].values.tolist())
    metrics.append(('Unique lemmas', lemmas_curras, lemmas_pacl))

    pos_curras = get_pos(lexicon_curras)
    pos_pacl = get_pos(pacl)
    metrics.append(['Unique POS', pos_curras, pos_pacl])

    roots_curras = set()
    roots_pacl = set([root for root in pacl['ROOT'].values.tolist() if root != 'NTWS'])
    metrics.append(['Unique roots', roots_curras, roots_pacl])

    root2lemma, root2lemma_unique = {}, {}
    for _, row in pacl.iterrows():
        if row['ROOT'].strip() != 'NTWS':
            root2lemma.setdefault(row['ROOT'], []).append(row['LEMMA'])
            root2lemma_unique.setdefault(row['ROOT'], set()).add(
                (row['LEMMA'].strip(), row['ANALYSIS'].split(':')[0].strip()))
    metrics.append(['Entries per root', [], sum(len(x) for x in root2lemma.values()) / len(root2lemma)])
    metrics.append(['Unique lemma:POS per root', [], sum(len(x) for x in root2lemma_unique.values()) / len(root2lemma_unique)])

    inflected_entries_curras = lexicon_curras['FORM'].values.tolist()
    inflected_entries_pacl = [form for form, analysis in pacl[['FORM', 'ANALYSIS']].values.tolist() if 'PHRASE' not in analysis]
    metrics.append(['All inflected forms', inflected_entries_curras, inflected_entries_pacl])

    unique_inflected_entries_curras = set(inflected_entries_curras)
    unique_inflected_entries_pacl = set(inflected_entries_pacl)
    metrics.append(['Unique inflected forms', unique_inflected_entries_curras, unique_inflected_entries_pacl])

    lexpos_features_curras = get_lexpos_features(lexicon_curras)
    lexpos_features_pacl = get_lexpos_features(pacl)
    metrics.append(['Unique lemma:POS:features', lexpos_features_curras, lexpos_features_pacl])

    pos_features_curras = get_pos_features(lexicon_curras)
    pos_features_pacl = get_pos_features(pacl)
    metrics.append(['Unique POS:features', pos_features_curras, pos_features_pacl])

    phrase_entries_curras = set()
    phrase_entries_pacl = pacl[pacl['ANALYSIS'].str.contains('PHRASE')]['FORM'].values.tolist()
    metrics.append(['All phrase entries', phrase_entries_curras, phrase_entries_pacl])
    
    phrases_curras = set()
    phrases_pacl = set(pacl[pacl['ANALYSIS'].str.contains('PHRASE')]['FORM'].values.tolist())
    metrics.append(['Unique phrases', phrases_curras, phrases_pacl])

    lexpos_phrases_curras = set()
    lexpos_phrases_pacl = set([(x[0].strip(), x[1].replace(' ', '')) for x in pacl[pacl['ANALYSIS'].str.contains('PHRASE')][['LEMMA', 'ANALYSIS']].values.tolist()])
    metrics.append(['Unique lemma:POS', lexpos_phrases_curras, lexpos_phrases_pacl])

    pos_phrases_curras = set()
    pos_phrases_pacl = set([x.replace(' ', '') for x in pacl[pacl['ANALYSIS'].str.contains('PHRASE')]['ANALYSIS'].values.tolist()])
    metrics.append(['Unique POS', pos_phrases_curras, pos_phrases_pacl])

    sheet = sh.worksheet('Stats-POS-Dist-2')
    sheet.batch_update([{
        'range': 'B9:D24', 
        'values': [[m[0], len(m[2]) if type(m[2]) in [set, list] else m[2], len(m[1]) if len(m[1]) else 'N/A'] for m in metrics]}])


# pacl = utils.read_pacl_as_df()
# pacl_dfs = utils.read_pacl_as_dfs()
sh = sa.open('Maknuune-Release-Camera-Ready')
sheet = sh.worksheet('Maknuune-v1.0')
pacl = pd.DataFrame(sheet.get_all_records()).astype(str)
pacl_obj = pacl.select_dtypes(['object'])
pacl[pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
pacl = pacl.replace(nan, '', regex=True)

sh = sa.open('PACL-Letter-Split')
        
curras = pd.read_csv('data/curras-16-04-22.csv')

pos_dist1(pacl, curras)
# pos_dist2(pacl)
# pos_dist3(pacl, curras)

pass
