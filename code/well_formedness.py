import re
from tqdm import tqdm

import pandas as pd
from numpy import nan
import gspread

from camel_tools.utils.charmap import CharMapper

import utils

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

defective = set(['و', 'ي'])

consonants_bw = "'|>&<}bptvjHxd*rzs$SDTZEgfqklmnhwy"
consonants_ar = bw2ar(consonants_bw)
consonants_no_def_bw = "'|>&<}bptvjHxd*rzs$SDTZEgfqklmnh"
consonants_no_def_ar = bw2ar(consonants_no_def_bw)
consonants_no_def_madda_bw = "'>&<}bptvjHxd*rzs$SDTZEgfqklmnh"
consonants_no_def_madda_ar = bw2ar(consonants_no_def_madda_bw)
valid_radicals_bw = "'btvjHxd*rzs$SDTZEgfqklmnhwy"
valid_radicals_ar = bw2ar(valid_radicals_bw)
hamzas_bw = "|>&<}"
hamzas_ar = bw2ar(hamzas_bw)
hamzat_wasl_bw = '{'
hamzat_wasl_ar = bw2ar(hamzat_wasl_bw)
diacritics_no_gem_bw = "aoiu"
diacritics_no_gem_ar = bw2ar(diacritics_no_gem_bw)
shadda_ar = bw2ar('~')
fatHa_ar, kasra_ar, Damma_ar, sukuwn_ar = bw2ar('a'), bw2ar('i'), bw2ar('u'), bw2ar('o')
tanwyn_ar = bw2ar('F')
Alif_ar = bw2ar('A')
aw_ar = bw2ar('aw')
ay_ar = bw2ar('ay')
iA_ar = bw2ar('iA')
sukuwn_ar = bw2ar('o')
oo_regex = re.compile(f'{aw_ar}(?!{sukuwn_ar})')
ee_regex_ay = re.compile(f'{ay_ar}(?!{sukuwn_ar})')
ee_regex_iA = re.compile(f'{iA_ar}(?!{sukuwn_ar})')

POS = {"ABBREV", "ADJ", "ADJ_COMP", "ADJ_NUM", "ADV", "ADV_INTERROG", "ADV_REL", "CONJ", "CONJ_SUB", "DIGIT", "FORIEGN", "INTERJ", "NOUN", "NOUN_NUM", "NOUN_PROP", "NOUN_QUANT", "PART", "PART_CONNECT", "PART_DET", "PART_EMPHATIC",
       "PART_FOCUS", "PART_FUT", "PART_INTERROG", "PART_NEG", "PART_PROG", "PART_RC", "PART_RESTRICT", "PART_VERB", "PART_VOC", "PREP", "PRON", "PRON_DEM", "PRON_EXCLAM", "PRON_INTERROG", "PRON_REL", "PUNC", "VERB", "VERB_NOM", "VERB_PSEUDO",
       "NOUN_ACT", "NOUN_PASS", "ADJ/NOUN", "UNKNOWN"}

essential_columns = ['ROOT', 'LEMMA', 'FORM', 'CAPHI++', 'ANALYSIS', 'GLOSS']

def _root_well_formedness_check(root, lemma_norm):
    if not root:
        return 'root-empty'

    message = ''
    if root != 'NTWS':
        if not bool(re.match(f'^([{consonants_ar}]\\.)' + '{1,3}' + f'[{consonants_ar}]$', root)):
            message += 'root-invalid'
        
        if not all(r in lemma_norm for r in root.split('.') if r not in defective):
            message += (' ' if message else '') + 'possible-root-lemma-mismatch'

        if root.replace('.', '') not in msa_roots:
            message += (' ' if message else '') + 'root-not-msa'

    return message


def _caphi_well_formedness_check(caphi):
    expansions = _get_caphi(caphi.replace('II', '||'))
    for caphi_split in expansions:
        if not all(cc in caphi_inventory for c in caphi_split for cc in c.split('||')):
            return 'caphi-invalid-char'

        tags = ''.join(caphi_inventory[c.split('||')[0]] if '||' in c else caphi_inventory[c]
                        for c in caphi_split)
        match = re.search(r'c{4,}|v{2,}', tags)
        if match:
            return 'caphi-invalid-seq'
    
    return ''

def _get_caphi(caphi):
    expansions = []
    for caphi_ in caphi.split(','):
        caphi_ = caphi_.strip()
        caphi_split = caphi_.split()
        expansions_ = [caphi_split]
        if '||' in caphi_:
            expansions_ = _expand_caphi(caphi_split)
        expansions += expansions_
    
    return expansions

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


def _aspect_paradigm_completion_well_formedness_check(lexicon_split, status_split):
    aspect2lemmas = {}
    for i, row in lexicon_split.iterrows():
        if re.match(r'^VERB:[PIC]$', row['ANALYSIS'].strip()):
            aspect2lemmas.setdefault(row['ANALYSIS'], {}).setdefault(row['LEMMA'], []).append(i)
    
    for asp, lemmas in aspect2lemmas.items():
        for lemma, indexes in lemmas.items():
            if len(indexes) > 1:
                for index in indexes:
                    status_split[index] += (' ' if status_split[index] else '') + f"more-than-one:{indexes[0]}"
    
    aspect2lemmas['VERB:IC'] = {}
    for aspect2lemmas_ in [aspect2lemmas['VERB:I'], aspect2lemmas['VERB:C']]:
        for lemma, indexes in aspect2lemmas_.items():
            x = aspect2lemmas['VERB:IC'].setdefault(lemma, [])
            x += indexes

    for perm in [('VERB:C', 'VERB:I'), ('VERB:I', 'VERB:C'), ('VERB:P', 'VERB:IC'), ('VERB:IC', 'VERB:P')]:
        for lemma in set(aspect2lemmas[perm[0]]) - set(aspect2lemmas[perm[1]]):
            indexes = aspect2lemmas[perm[0]][lemma]
            for index in indexes:
                status_split[index] += (' ' if status_split[index] else '') + f"missing:{perm[1]}"


def _nom_paradigm_completion_well_formedness_check(lexicon_split, status_split):
    lemma2info = {}
    for i, row in lexicon_split.iterrows():
        if re.match(r'NOUN:', row['ANALYSIS']):
            lemma2info.setdefault(row['LEMMA'], []).append((row['ANALYSIS'], i))
    
    missing_cases = [[row[1] for row in info]
                     for info in lemma2info.values()
                     if 'NOUN:PL' in info[0] and len({'NOUN:MS', 'NOUN:FS'} & set(info[0])) == 0]

    for missing_case in missing_cases:
        for index in missing_case:
            status_split[index] += (' ' if status_split[index] else '') + f"missing-singular:{missing_case[0]}"
    pass


def _lemma_form_well_formedness_check(lexicon_split, status_split):
    lemma2forms = {}
    for i, row in lexicon_split.iterrows():
        lemma2forms.setdefault(row['LEMMA'], []).append((row['FORM'], i))

    missing_cases = [[row[1] for row in forms]
                     for lemma, forms in lemma2forms.items() if lemma not in [form[0] for form in forms]]

    for missing_case in missing_cases:
        for index in missing_case:
            status_split[index] += (' ' if status_split[index] else '') + f"missing-lemma-form:{missing_case[0]}"
    pass


def _diacritization_check(text, field, caphi, is_phrase):
    message = ''
    if re.search(f'[{consonants_no_def_madda_ar}][{consonants_no_def_madda_ar}]', text):
        message += (' ' if message else '') + f'{field}:more-than-2-consec-cons'
    #TODO: fix so that it works on two letter sequences like $w
    if re.search(f'[{diacritics_no_gem_ar}][{diacritics_no_gem_ar}]', text):
        message += (' ' if message else '') + f'{field}:consecutive-diacritics'
    if re.search(f"(?<!{diacritics_no_gem_ar[diacritics_no_gem_bw.index('i')]})[ي][{consonants_no_def_ar}]", text) or \
       re.search(f"(?<!{diacritics_no_gem_ar[diacritics_no_gem_bw.index('u')]})[و][{consonants_no_def_ar}]", text):
        if not ee_regex_ay.search(text) and not oo_regex.search(text):
            message += (' ' if message else '') + f'{field}:defective-no-diac'
    if re.search(f"^{hamzat_wasl_ar}", text):
        message += (' ' if message else '') + f'{field}:hamzat-wasl'
    if not is_phrase and 'oo' in caphi and 'و' in text and not oo_regex.search(text):
        message += (' ' if message else '') + f'{field}:oo-possible-mistake'
    if not is_phrase and 'ee' in caphi and ('ي' in text and not ee_regex_ay.search(text) or 'ا' in text and not ee_regex_iA.search(text)):
        message += (' ' if message else '') + f'{field}:ee-possible-mistake'
    if not is_phrase and text[-1] != shadda_ar and re.search(r'([^ ]+) \1$', caphi):
        message += (' ' if message else '') + f'{field}:possible-final-gem-missing'
    
    return message


def _duplicates_check(lexicon_split, status_split):
    entry2indexes_caphi = {}
    for i, row in lexicon_split.iterrows():
        analysis = ':'.join(x.strip() for x in row['ANALYSIS'].split(':'))
        entry2indexes_caphi.setdefault((analysis, row['LEMMA'], row['FORM']), []).append((i, row['CAPHI++']))
    
    for entry, indexes_caphi in entry2indexes_caphi.items():
        if len(indexes_caphi) > 1:
            caphi2indexes = {}
            for index, caphi in indexes_caphi:
                caphi2indexes.setdefault(caphi, []).append(index)
            
            for caphi, indexes in {caphi: indexes for caphi, indexes in caphi2indexes.items() if len(indexes) > 1}.items():
                for index in indexes:
                    status_split[index] += (' ' if status_split[index] else '') + f"possible-duplicates:{indexes[0]}"
            
            key = next(iter(caphi2indexes))
            index_select = caphi2indexes[key][0]
            for caphi, indexes in {caphi: indexes for caphi, indexes in caphi2indexes.items() if len(indexes) == 1}.items():
                for index in indexes:
                    status_split[index] += (' ' if status_split[index] else '') + f"possible-caphi-duplicates:{index_select}"


def well_formedness(lexicon_split,
                    spreadsheet,
                    sheet,
                    root=False,
                    caphi=True,
                    diacritics=True,
                    aspect_paradigm=True,
                    nom_paradigm=True,
                    lemma_form=True,
                    duplicates=True,
                    write_status=True):
    status_split = []
    for _, row in lexicon_split.iterrows():
        message = ''
        root, lemma_norm = row['ROOT'], row['LEMMA_NORM']
        caphi = row['CAPHI++']
        if root:
            message += _root_well_formedness_check(root, lemma_norm)
        if caphi:
            message += (' ' if message else '') + _caphi_well_formedness_check(caphi)
        
        if row['ANALYSIS'].split(':')[0] not in POS:
            message += (' ' if message else '') + 'faulty-analysis'
        for c in essential_columns:
            if row[c].strip() == '':
                message += (' ' if message else '') + f'missing-{c}'
        
        for f in ['form', 'lemma']:
            is_phrase = 'PHRASE' in row['ANALYSIS']
            if f == 'form' and is_phrase:
                continue
            text = row[f.upper()]
            if not text:
                message += (' ' if message else '') + f'{f}-missing'
                continue

            if diacritics:
                #TODO: at some point debug without these
                if text[0] == 'أ' and text[1] != 'َ' and text[1] != 'ُ':
                    text = re.sub(r'^أ', 'أَ', text)
                elif text[0] == 'إ' and text[1] != 'ِ':
                    text = re.sub(r'^إ', 'إِ', text)
                elif f =='form' and row['ANALYSIS'] == 'VERB:I' and text[0] == 'ي' and text[1] not in 'َُِْ':
                    text = re.sub(r'^ي', 'يْ', text)
                
                message += (' ' if message else '') + _diacritization_check(text, f, caphi, is_phrase)
        
        status_split.append(message)

    if aspect_paradigm:
        _aspect_paradigm_completion_well_formedness_check(lexicon_split, status_split)
    if nom_paradigm:
        _nom_paradigm_completion_well_formedness_check(lexicon_split, status_split)
    if lemma_form:
        _lemma_form_well_formedness_check(lexicon_split, status_split)
    if duplicates:
        _duplicates_check(lexicon_split, status_split)
    
    if write_status:
        utils.add_check_mark_online(lexicon_split, spreadsheet, sheet, write='overwrite',
                                    messages=status_split, status_col_name='STATUS_CHRIS')
    pass

def get_caphi_symbols_inventory():
    caphi_inventory = pd.read_csv('caphi_table.csv')
    caphi_consonants = ['Q', 'D', 'J', 'Z', 'T', 'S', 'Z.', 'D.', 'K'] + \
                        caphi_inventory['CAPHI'][caphi_inventory['Type'] == 'consonant'].values.tolist()
    caphi_consonants_set = set(caphi_consonants)
    caphi_vowels = ['aa', 'u', 'o', 'oo', 'uu', 'aa.', 'a.'] + \
                    caphi_inventory['CAPHI'][caphi_inventory['Type'] == 'vowel'].values.tolist()
    caphi_vowels_set = set(caphi_vowels)
    caphi2type, type2caphi = {}, {}
    caphi2type.update({c: 'c' for c in caphi_consonants_set})
    caphi2type.update({v: 'v' for v in caphi_vowels_set})
    caphi2type.update({'#': '#'})
    type2caphi.update({'c': caphi_consonants_set, 'v': caphi_vowels_set, '#':'#'})
    return caphi2type, type2caphi

if __name__ == "__main__":
    # lexicon_sheets = [
    #     ('PACL-Alif-Kha-Group-1', 'Alif-Kha'),
    #     ('PACL-Dal-Shin-Group-2', 'Dal-Shin'),
    #     ('PACL-Sad-Qaf-Group-3','Sad-Qaf'),
    #     ('PACL-Kaf-Ya-Group-4', 'Kaf-Ya')
    # ]
    msa_roots = pd.read_csv(
        '/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/camel_morph/misc_files/Roots.csv')
    msa_roots = msa_roots.replace(nan, '', regex=True)
    msa_roots = set(msa_roots['ROOT'].values.tolist())

    caphi_inventory, _ = get_caphi_symbols_inventory()

    sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
    # sh = sa.open('PACL-Letter-Split')
    # sheet_names = utils.sheet_names
    sh = sa.open('Maknuune-WIP')
    sheet_names = ['Maknuune-v1.1']
    # sheet_names = ['Maknuune-WIP-Add']

    for sheet_name in tqdm(sheet_names):
        sheet = sh.worksheet(sheet_name)
        lexicon = pd.DataFrame(sheet.get_all_records()).astype(str)
        lexicon = lexicon.replace(nan, '', regex=True)
        lexicon['LEMMA_NORM'] = lexicon.apply(
            lambda row: re.sub(f'[{hamzas_ar}]', bw2ar("'"), row['LEMMA']), axis=1)
        lexicon['LEMMA_NORM'] = lexicon.apply(
            lambda row: re.sub(f"^{bw2ar('A')}", bw2ar("'"), row['LEMMA_NORM']), axis=1)
        utils.try_google_api_until_succeded(well_formedness, lexicon, sh, sheet)

