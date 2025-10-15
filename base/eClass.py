import os
import csv
import pandas as pd
from random import randint
import enchant
from quantulum3 import parser
import numpy as np

class MapEClass():
    def __init__(self): 
        pass

    def get_units(self): ## get unit classes information from eClass and save in dataframe
        unit_classes = ['PreferredName', 'ShortName', 'Definition', 'Source', 'Comment', 'SINotation', 'SIName',
                        'DINNotation', 'ECEName', 'ECECode', 'NISTName', 'IECClassification', 'IrdiUN',
                        'NameOfDedicatedQuantity']
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_UN_en.csv") 
        file = open(file_path, encoding='utf-8')
        csvreader = csv.reader(file)
        next(csvreader)  # Read and skip the header
        units = []
        for row in csvreader: #Read each row in the CSV file and split its contents into separate cells using (;) and store units.
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                units.append(cell)
        file.close()
        unit_list = pd.DataFrame(units, columns=unit_classes)
        return unit_list

    def get_classes(self):
        classes_ = ['Supplier', 'IdCC', 'Identifier', 'VersionNumber', 'VersionDate', 'RevisionNumber', 'CodedName',
                    'PreferredName', 'Definition', 'ISOLanguageCode', 'ISOCountryCode', 'Note', 'Remark', 'Level',
                    'MKSubclass', 'MKKeyword', 'IrdiCC']
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_CC_en.csv") 
        file = open(file_path, encoding='utf-8')
        csvreader = csv.reader(file)
        next(csvreader)
        units = []
        for row in csvreader:
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                units.append(cell)
        file.close()
        class_list = pd.DataFrame(units, columns=classes_)
        return class_list

    def get_properties(self): 
        properties_class = ['Supplier', 'IdPR', 'Identifier', 'VersionNumber', 'VersionDate', 'RevisionNumber',
                            'PreferredName', 'ShortName', 'Definition', 'SourceOfDefinition', 'Note', 'Remark',
                            'PreferredSymbol', 'IrdiUN', 'ISOLanguageCode', 'ISOCountryCode', 'Category',
                            'AttributeType', 'DefinitionClass', 'DataType', 'IrdiPR', 'CurrencyAlphaCode']

        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_PR_en.csv") 
        file = open(file_path, encoding='utf-8') 
        csvreader = csv.reader(file)
        next(csvreader)
        properties = []
        for row in csvreader:
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                properties.append(cell)
        file.close()
        property_list = pd.DataFrame(properties, columns=properties_class)
        return property_list

    def get_IrdiCC_descr(self, class_name):
        # get IrdiCC for a class
        classes = self.get_classes()
        index_similar_name = []
        levenshtein_distance = []

        for ind in classes.index:
            # if class name is right in eClass, return the corresponding IrdiCC
            if class_name.lower() == classes['PreferredName'][ind].lower():
                IrdiCC = classes['IrdiCC'][ind]
                descr = [str(classes['PreferredName'][ind]), str(classes['Definition'][ind])]
                return IrdiCC, descr
            # if class name is similar to the name in eClass, save all the similar names, namely their index, in a list
            if class_name.lower() in classes['PreferredName'][ind].lower():
                index_similar_name.append(ind)

        # get the most similar name in eClass with the class name
        # use levenshtein distance to calculate the distance of two strings
        for ind in index_similar_name:
            levenshtein_distance.append(enchant.utils.levenshtein(class_name, classes['PreferredName'][ind]))
        # if the levenshtein distance list is not empty, get the least levenshtein distance
        if levenshtein_distance:
            index_name_found = index_similar_name[np.argmin(levenshtein_distance)]
            # return the IrdiCC of the most similar class name found in eClass
            IrdiCC = classes['IrdiCC'][index_name_found]
            descr = [str(classes['PreferredName'][index_name_found]), str(classes['Definition'][index_name_found])]
            return IrdiCC, descr
        # if the distance list is empty, set IrdiCC to zero and ask engineer to change the IrdiCC manually
        else:
            IrdiCC = "0000"
            return IrdiCC, "No semantic ID is found, please add it manually."

    def extract_unit(self, sent):
        # get unit from a sentence
        quants = parser.parse(sent)
        if quants:
            if quants[0].unit.name == "dimensionless":
                return sent, None
            else:
                return quants[0].value, quants[0].unit.name
        else:
            return sent, None

    def get_IrdiPR_unit_descr(self, prop_name):
        # get IrdiPR and unit for a property
        properties = self.get_properties()
        units = self.get_units()

        index_similar_name = []
        levenshtein_distance = []
        unit = ''
        descr = []
        # found the similar name and return the IrdiUN and unit of property
        for ind in properties.index:
            # if property name is right in eClass, return the corresponding IrdiPR and unit
            if prop_name.lower() == properties['PreferredName'][ind].lower():
                IrdiUN, IrdiPR = properties['IrdiUN'][ind], properties['IrdiPR'][ind]
                for i in units.index:
                    if IrdiUN == units['IrdiUN'][i]:
                        unit = units['PreferredName'][i]
                        descr = [str(properties['PreferredName'][i]), str(properties['Definition'][i]), unit]
                        return unit, IrdiPR, descr
            # if property name is similar to the name in eClass, save all the similar names, namely their index, in a list
            if prop_name.lower() in properties['PreferredName'][ind].lower():
                index_similar_name.append(ind)

        # get the most similar name in eClass with the property name
        # use levenshtein distance to calculate the distance of two strings
        for ind in index_similar_name:
            levenshtein_distance.append(enchant.utils.levenshtein(prop_name, properties['PreferredName'][ind]))
        # if the levenshtein distance list is not empty, get the least levenshtein distance
        if levenshtein_distance:
            index_name_found = index_similar_name[np.argmin(levenshtein_distance)]
            # return the unit and IRdiPR of the most similar property name found in eClass
            IrdiUN, IrdiPR = properties['IrdiUN'][index_name_found], properties['IrdiPR'][index_name_found]
            for i in units.index:
                if IrdiUN == units['IrdiUN'][i]:
                    unit = units['PreferredName'][i]
            descr = [str(properties['PreferredName'][index_name_found]),
                     str(properties['Definition'][index_name_found]), unit]
            return unit, IrdiPR, descr
        # if the distance list is empty, set IrdiPR to zero and ask engineer to change the IrdiPR manually
        else:
            unit, IrdiPR = None, "0000"
            descr = "No semantic ID is found, please add it manually."
            return unit, IrdiPR, descr

    def convert_unit(self, unit_convert, unit, value):
        # convert unit to the standard unit
        # a table of unit convertion
        units = [['pascal', 'bar', '*', 1e5],
                 ['pascal', 'megapascal', '*', 1e6],
                 ['megapascal', 'bar', '*', 10],
                 ['kelvin', 'degree Celsius', '+', -273.16],
                 ['meter', 'millimetre', '*', 1e3],
                 ['square meter', 'square millimetre', '*', 1e6]]
        conv_table = pd.DataFrame(units, columns=['unit_conv', 'unit', 'operator', 'multiplier'])

        # convert unit to the standard unit according to the table
        for ind in conv_table.index:
            if unit_convert.lower() == conv_table['unit_conv'][ind].lower() \
                    and unit.lower() == conv_table['unit'][ind].lower():
                if conv_table['operator'][ind] == '*':
                    value *= conv_table['multiplier'][ind]
                elif conv_table['operator'][ind] == '+':
                    value += conv_table['multiplier'][ind]
            if unit_convert.lower() == conv_table['unit'][ind].lower() \
                    and unit.lower() == conv_table['unit_conv'][
                ind].lower():
                if conv_table['operator'][ind] == '*':
                    value /= conv_table['multiplier'][ind]
                elif conv_table['operator'][ind] == '+':
                    value -= conv_table['multiplier'][ind]
        return value