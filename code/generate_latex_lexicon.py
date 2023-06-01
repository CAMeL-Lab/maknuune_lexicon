import re

import pandas as pd
from numpy import nan
import gspread

GLOSS_DELIM_RE = re.compile(r'[;#]')
CAPHI_DELIM_RE = re.compile(r'[,#]')
LATIN_SCRIPT = re.compile(r'[a-zA-Z]')
QUOTES = re.compile(r'"([^"]+)"')

from camel_tools.utils.charmap import CharMapper

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

DIGITS_MAP = {'0': '۰', '1': '١', '2': '٢', '3': '٣', '4': '٤',
              '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'}

feat2fancy = {'ms': 'm.', 'fs': 'f.', 'verb:i': 'i.', 'verb:c': 'c.', 'verb:p': 'p.', 'p': 'pl.', 'mp': 'pl.', 'fp': 'f.pl.'}

begin_document = """
\\documentclass[10pt,a4paper,twoside]{article} % 10pt font size, A4 paper and two-sided margins
\\usepackage{preamble}
\\usepackage{standalone}

\\begin{document}
"""

end_document = """
\\end{document}
"""

BULLET = "\\ $\\bullet$\\ \\ "
LOZENGE = "\\ $\\smblkdiamond$\\ \\ "
CAPHI_SPECIAL_CHARS = {'Q', 'D', 'J', 'Z', 'T', 'S', 'Z.', 'D.', 'K'}

NOTES_RE = re.compile(r'loanword|unit noun|collective noun|mass noun|approving|disapproving|taboo|impolite')

def digits_map(digit):
    return ''.join(DIGITS_MAP[d] for d in str(digit))


def text2latex_ar(text):
    text_ = []
    for t in text.split():
        if LATIN_SCRIPT.search(t):
            text_.append(('l', t))
        else:
            text_.append(('a', t))
    
    text, chunk = [], []
    if text_:
        script_prev = text_[0][0]
        for script_, t in text_:
            if script_ != script_prev and chunk:
                text.append(f"\\foreignlanguage{{arabic}}{{{' '.join(chunk)}}}"
                                if script_prev == 'a' else ' '.join(chunk))
                chunk = []    
            chunk.append(t)
            script_prev = script_
        text.append(f"\\foreignlanguage{{arabic}}{{{' '.join(chunk)}}}"
                                if script_prev == 'a' else ' '.join(chunk))

    return ' '.join(text)

def get_sub_ipa(caphi_sub, ipapp=True, tipa=False):
    if ipapp:
        ipa_ = ''.join(caphi2ipa.get(c, '\\#') for c in caphi_sub)
        return f"\\textipa{{{ipa_}}}" if tipa else f"{{\\sffamily {ipa_}}}"
    chunk = []
    char_ipa_prev = caphi_sub[0] not in CAPHI_SPECIAL_CHARS
    ipa_output = []
    for i, c in enumerate(caphi_sub):
        char_ipa = c not in CAPHI_SPECIAL_CHARS
        if char_ipa != char_ipa_prev and chunk:
            ipa_ = ''.join(caphi2ipa.get(c, '\\#') if c != '.' else '.' for c in chunk)
            ipa_output.append(f"\\textipa{{{ipa_}}}" if char_ipa_prev else ipa_)
            chunk = []
        # For gemination
        elif c == caphi_sub[i - 1]:
            chunk.append('.')
        chunk.append(c)
        char_ipa_prev = char_ipa
    ipa_ = ''.join(caphi2ipa.get(c, '\\#') if c != '.' else '.' for c in chunk)
    ipa_output.append(f"\\textipa{{{ipa_}}}" if char_ipa_prev else ipa_)
    return ''.join(ipa_output)

def get_ipa(caphis):
    ipa = []
    for caphi in set(caphis):
        assert not (',' in caphi and '#' in caphi)
        ipa.append([])
        for caphi_sub in CAPHI_DELIM_RE.split(caphi):
            ipa[-1].append([])
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
                ipa[-1][-1] = ', '.join(caphi_subs)
            else:
                ipa[-1][-1] = get_sub_ipa(caphi_sub)
        ipa[-1] = f"{', ' if ',' in caphi else ' '}".join(ipa[-1])
    
    return ', '.join(ipa)


def generate_entry(form2rows, pos, phrases):
    index = 1
    examples = []
    entry = '{'
    gloss_lemma = GLOSS_DELIM_RE.split(form2rows[0][1][0]['GLOSS'].replace('_[auto]', '').replace('_', ' '))
    source_lemma = form2rows[0][1][0]['SOURCE']
    msa_lemma = GLOSS_DELIM_RE.split(form2rows[0][1][0]['GLOSS_MSA'].replace('_[auto]', '').replace('_', ' '))
    used_notes = set()
    for i, (_, rows) in enumerate(form2rows):
        if i:
            entry += BULLET
        entry += f"\\setlength\\topsep{{0pt}}\\textbf{{\\foreignlanguage{{arabic}}{{{rows[0]['FORM']}}}}}"
        if rows[0]['NOTES'] and NOTES_RE.search(rows[0]['NOTES']):
            used_notes.add(rows[0]['NOTES'])
            entry += f"\\footnote{{{rows[0]['NOTES'].replace('_', ' ').capitalize()}}}\\ "
        entry += '\\ '

        feat2rows = {}
        for row in rows:
            analysis = row['ANALYSIS'].split(':')
            feat = analysis[1].lower() if len(analysis) > 1 else ''
            feat2rows.setdefault(feat, []).append(row)

        ipa = get_ipa([row['CAPHI++'] for row in rows])
        entry += f"{{\\color{{gray}}\\texttt{{/{ipa}/}}\\color{{black}}}}\\ "
        
        pos_ = pos.replace('_', '\\textunderscore ')
        entry += f'\\textsc{{{pos_}}}\\ ' if i == 0 else ''

        for feat, rows in feat2rows.items():
            if feat:
                feat = f'verb:{feat}' if pos == 'verb' else feat
                entry += '[' + feat2fancy.get(feat, feat) + ']\\ '
            
            for j, row in enumerate(rows):
                if j and len(rows) > 1:
                    entry += LOZENGE
                    entry += f"\\setlength\\topsep{{0pt}}\\textbf{{\\foreignlanguage{{arabic}}{{{rows[0]['FORM']}}}}}\\ "
                    if row['NOTES'] and row['NOTES'] not in used_notes and NOTES_RE.search(row['NOTES']):
                        used_notes.add(rows[0]['NOTES'])
                        entry += f"\\footnote{{{rows[0]['NOTES'].replace('_', ' ').capitalize()}}}\\ "

                if (i == 0 or row['SOURCE'] != source_lemma) and row['SOURCE']:
                    source = row['SOURCE'].strip()
                    source = text2latex_ar(QUOTES.sub(r'»\1«', source))
                    entry += f'(src. \\color{{gray}}{source}\\color{{black}})\\ '

                if row['GLOSS_MSA']:
                    msa_glosses = [x for x in GLOSS_DELIM_RE.split(QUOTES.sub(r'»\1«', row['GLOSS_MSA'].replace('_', ' '))) if i == 0 or x not in msa_lemma]
                    if msa_glosses:
                        msa_glosses = ' '.join(reversed([((' .' if len(g.split()) > 1 else ' ') if i != len(msa_glosses) else '') + f'{text2latex_ar(g.strip())}~\\foreignlanguage{{arabic}}{{\\textbf{{{digits_map(i)}.}}}}'
                                    for i, g in enumerate(msa_glosses, start=1)]))
                        entry += f'\\color{{gray}}(msa. {msa_glosses}\\color{{black}})\\ '
                
                glosses = [x for x in GLOSS_DELIM_RE.split(row['GLOSS'].replace('_[auto]', '').replace('_', ' ')) if i == 0 or x not in gloss_lemma]
                if glosses:
                    glosses = ' '.join(f'\\textbf{{{i}.}}~{g.strip()}' + (('. ' if len(g.split()) > 1 else ' ') if i != len(glosses) else '')
                            for i, g in enumerate(glosses, start=1))
                    entry += f'{glosses}\\ '
                
                if row['EXAMPLE_USAGE']:
                    examples_ = GLOSS_DELIM_RE.split(QUOTES.sub(r'»\1«', row['EXAMPLE_USAGE'].replace('_', ' ')))
                    if examples_:
                        for example_ in examples_:
                            index += 1
                            examples.append(f'{example_}{BULLET}')

    if phrases:
        entry += BULLET
        for i, (_, rows) in enumerate(phrases.items()):
            for j, row in enumerate(rows):
                entry += f"\\textsc{{ph.}} \\color{{gray}} \\foreignlanguage{{arabic}}{{{row['FORM']}}}\\color{{black}}\\ "
                if row['NOTES'] and row['NOTES'] not in used_notes and NOTES_RE.search(row['NOTES']):
                    used_notes.add(rows[0]['NOTES'])
                    entry += f"\\footnote{{{rows[0]['NOTES'].replace('_', ' ').capitalize()}}}\\ "
                
                ipa = get_ipa([row['CAPHI++'] for row in rows])
                entry += f"{{\\color{{gray}}\\texttt{{/{ipa}/}}\\color{{black}}}}\\ "
                if (i == 0 or row['SOURCE'] != source_lemma) and row['SOURCE']:
                    source = row['SOURCE'].strip()
                    source = text2latex_ar(QUOTES.sub(r'»\1«', source))
                    entry += f'(src. \\color{{gray}}{source}\\color{{black}})\\ '
                
                if row['GLOSS_MSA']:
                        msa_glosses = [x for x in GLOSS_DELIM_RE.split(QUOTES.sub(r'»\1«', row['GLOSS_MSA'].replace('_', ' '))) if i == 0 or x not in msa_lemma]
                        if msa_glosses:
                            msa_glosses = ' '.join(reversed([((' .' if len(g.split()) > 1 else ' ') if i != len(msa_glosses) else '') + f'{text2latex_ar(g.strip())}~\\foreignlanguage{{arabic}}{{\\textbf{{{digits_map(i)}.}}}}'
                                        for i, g in enumerate(msa_glosses, start=1)]))
                            entry += f'\\color{{gray}} (msa. {msa_glosses})\\color{{black}}\\ '
                    
                glosses = [x for x in GLOSS_DELIM_RE.split(row['GLOSS'].replace('_[auto]', '').replace('_', ' ')) if i == 0 or x not in gloss_lemma]
                if glosses:
                    glosses = ' '.join(f'\\textbf{{{i}.}}~{g.strip()}' + (('. ' if len(g.split()) > 1 else ' ') if i != len(glosses) else '')
                            for i, g in enumerate(glosses, start=1))
                    entry += f'{glosses}\\ '
                
                if row['EXAMPLE_USAGE']:
                    examples_ = GLOSS_DELIM_RE.split(QUOTES.sub(r'»\1«', row['EXAMPLE_USAGE'].replace('_', ' ')))
                    if examples_:
                        for example_ in examples_:
                            index += 1
                            examples.append(f'{example_}{BULLET}')
                
                entry += BULLET if (len(phrases) == 1 or i + 1 != len(phrases)) and (len(rows) == 1 or j + 1 != len(rows)) else ''

    if examples:
        examples = f'\\foreignlanguage{{arabic}}{{\\textbf{{\\underline{{\\foreignlanguage{{arabic}}{{أمثلة}}}}}}: ' + ' '.join(reversed(examples))[:-len(BULLET)] + '}'
        entry += f" \\begin{{flushright}}\\color{{gray}}{examples}\\end{{flushright}}\\color{{black}}"
    
    entry += '} \\vspace{2mm}'
    
    return entry


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


    sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
    # sh = sa.open('Copy of Maknuune-Release-Camera-Ready')
    # sheet = sh.worksheet('Maknuune-v1.0')
    sh = sa.open('Maknuune-Release-Camera-Ready-v1.0')
    sheet = sh.worksheet('Maknuune-v1.0.2')
    pacl = pd.DataFrame(sheet.get_all_records()).astype(str)
    pacl_obj = pacl.select_dtypes(['object'])
    pacl[pacl_obj.columns] = pacl_obj.apply(lambda x: x.str.strip())
    pacl = pacl.replace(nan, '', regex=True)
    pacl['CAPHI++'] = pacl.apply(lambda row: re.sub(r'II', '||', row['CAPHI++']), axis=1)
    pacl = pacl.replace('\"', '', regex=True)
    pacl = pacl.replace('%', '\\%', regex=True)
    # pacl.loc[pacl['ROOT'] == 'NTWS', 'ROOT'] = pacl.loc[pacl['ROOT'] == 'NTWS', 'ROOT_NTWS']

    first_radical2root2lemmapos2type2form2rows = {}
    for _, row in pacl.iterrows():
        ntws = True if row['ROOT'] == 'NTWS' else False
        root = row['ROOT'] if not ntws else row['ROOT_NTWS']
        lemmapos_rows = first_radical2root2lemmapos2type2form2rows.setdefault(
            root[0], {}).setdefault(
                (root, ' (ntws)' if row['ROOT'] == 'NTWS' else ''), {}).setdefault(
                    (row['LEMMA'], row['ANALYSIS'].split(':')[0].strip()), {'phrases': {}, 'other': {}})
        
        lemmapos_rows['phrases' if 'PHRASE' in row['ANALYSIS'] else 'other'].setdefault(
            row['FORM'], []).append(row.to_dict())

    first_radical2root2lemmapos2type2form2rows = dict(sorted(first_radical2root2lemmapos2type2form2rows.items(), key=lambda x: x[0]))

    errors = []
    
    for first_radical, root2lemmapos2type2form2rows in first_radical2root2lemmapos2type2form2rows.items():
        with open(f'/Users/chriscay/Library/Mobile Documents/com~apple~CloudDocs/NYUAD/palestinian_lexicon/maknuune_dict/letter_sections/{first_radical}.tex', 'w') as f:
            # if first_radical not in 'ء':
            #     continue
            print(begin_document, file=f)
            print(f"\\begin{{figure*}}[t!]\\centering\\includegraphics[width=0.15\\linewidth]{{letter_images/{first_radical}.png}}\\end{{figure*}}", file=f)
            print(f"\\color{{white}}", file=f)
            print('\n', f"\\section*{{\\foreignlanguage{{arabic}}{{{first_radical}}}}}" if first_radical != 'N' else f"\\section*{{NTWS}}", '\n', f"\\begin{{multicols}}{{2}}", '\n', file=f)
            print(f"\\addcontentsline{{toc}}{{section}}{{\\protect\\numberline{{}}\\foreignlanguage{{arabic}}{{{first_radical}}}}}%", file=f)
            print(f"\\color{{black}}", file=f)
            root2lemmapos2type2form2rows = dict(sorted(root2lemmapos2type2form2rows.items(), key=lambda x: x[0]))
            for (root, ntws), lemmapos2type2form2rows in root2lemmapos2type2form2rows.items():
                if root == 'NTWS':
                    raise NotImplementedError
                if root != 'NTWS':
                    root_ = f"\\color{{blue}}\\foreignlanguage{{arabic}}{{{root}}}\\color{{blue}}{{{ntws if ntws else ''}}}"
                    # root_flipped = f"\\foreignlanguage{{arabic}}{{{root}}}"
                    print('\\vspace{-3mm}', file=f)
                    print(f"\\markboth{{{root_}}}{{{root_}}}\\subsection*{{{root_}\\index{{{root_}}}}}", '\n', file=f)
                lemmapos2type2form2rows = dict(sorted(lemmapos2type2form2rows.items(), key=lambda x: x[0]))
                for (lemma, pos), type2form2rows in lemmapos2type2form2rows.items():
                    form2rows = type2form2rows['other']
                    if not form2rows:
                        errors.append(form2rows)
                        continue
                    form2rows_ = []
                    form2rows_ += [(form, rows) for form, rows in form2rows.items() if form == lemma]
                    form2rows_ += [(form, rows) for form, rows in form2rows.items() if form != lemma]
                    lemma_entry = generate_entry(form2rows_, pos.lower(), type2form2rows['phrases'])
                    print(lemma_entry, file=f)
                    print(file=f)
            print(f"\\end{{multicols}}", file=f)
            print(end_document, file=f)

    pass