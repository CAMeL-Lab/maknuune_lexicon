import re

from utils import read_pacl_as_df
from well_formedness import _diacritization_check, get_caphi_symbols_inventory

from camel_tools.utils.charmap import CharMapper

bw2ar = CharMapper.builtin_mapper('bw2ar')
ar2bw = CharMapper.builtin_mapper('ar2bw')

caphi2type, type2caphi = get_caphi_symbols_inventory()
pacl = read_pacl_as_df()

wrong = []
count, total = 0, 0
for _, row in pacl.iterrows():
    message = ''
    for i, text in enumerate([row['LEMMA'], row['FORM']]):
        text = text
        if text[0] == 'أ' and text[1] != 'َ':
            text = re.sub(r'^أ', 'أَ', text)
        elif text[0] == 'إ' and text[1] != 'ِ':
            text = re.sub(r'^إ', 'إِ', text)
        elif i and row['ANALYSIS'] == 'VERB:I' and text[0] == 'ي' and text[1] != 'ْ':
            text = re.sub(r'ي', 'يْ', text)
        message = _diacritization_check(text)
        if message:
            caphi = row['CAPHI++']
            caphi_cons = [x for x in caphi.split() if caphi2type(x) == 'c']
            wrong.append((message, row['LEMMA'], row['FORM'], row['CAPHI++'], row['ANALYSIS']))
    if message:
        total += 1
        count += 1 if re.sub(r'[ًٌٍَُِْ]', '', row['LEMMA']) != re.sub(r'[ًٌٍَُِْ]', '', row['FORM']) else 0

pass