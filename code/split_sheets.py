import os
import re

import pandas as pd
from numpy import nan
import numpy as np
import gspread

sa = gspread.service_account("/Users/chriscay/.config/gspread/service_account.json")
sh = sa.open('PACL-Letter-Split')

lexicon_sheets = [
    ('PACL-Alif-Kha-Group-1', 'Alif-Kha'),
    ('PACL-Dal-Shin-Group-2', 'Dal-Shin'),
    ('PACL-Sad-Qaf-Group-3','Sad-Qaf'),
    ('PACL-Kaf-Ya-Group-4', 'Kaf-Ya')
]
used = set()

i = 0
for spreadsheet, sheet in lexicon_sheets:
    lexicon = pd.read_csv(os.path.join('data', f'{sheet}.csv'), index_col=False)
    lexicon = lexicon.replace(nan, '', regex=True)
    # lexicon.insert(0, "ID", np.arange(lexicon.shape[0]) + 1)
    # lexicon = lexicon.loc[:, ~lexicon.columns.str.contains('^Unnamed')]
    letters = sorted(list(set([letter for letter in lexicon['Root #1'].values.tolist() if letter])))
    # letters = [letter for letter in letters if letter in ['ء']]
    for letter in letters:
        if letter not in used:
            lexicon_letter = lexicon[lexicon['Root #1'] == letter]
            lexicon_letter.insert(0, "ID", np.arange(lexicon_letter.shape[0]) + 1)
            lexicon_letter['Jihad-Lit'], lexicon_letter['Jihad-Trans'], lexicon_letter['Jihad-Comments'] = '', '', ''
            lexicon_letter = lexicon_letter.loc[:, ~lexicon_letter.columns.str.contains('^Unnamed')]
            root, root1 = lexicon_letter['ROOT'].values.tolist(), lexicon_letter['Root #1'].values.tolist()
            assert len(root) == len(root1) and all(x[0][0] == x[1] for x in zip(root, root1))
            sheet = sh.worksheet('Template')
            sheet = sh.duplicate_sheet(source_sheet_id=sheet.id,
                                       insert_sheet_index=i + 1,
                                       new_sheet_name=letter)
            sheet.update(
                [lexicon_letter.columns.values.tolist()] + lexicon_letter.values.tolist())
            used.add(letter)
            i += 1
        else:
            raise NotImplementedError

pass
