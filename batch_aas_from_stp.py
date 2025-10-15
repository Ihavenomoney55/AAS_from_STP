import os
import re
from typing import List, Optional

from basyx.aas import model
from basyx.aas.adapter import aasx

from base.create_ent import ent
from base.eClass import MapEClass

from batch_step_parser import BatchStepParser, ComponentNode


class BatchAASFromSTP:
    """Convert batch STEP data to unified AAS format"""
    
    def __init__(self, parser: BatchStepParser, output_filename: str):
        self.parser = parser
        self.output_filename = output_filename
        self.map_eclass = MapEClass()
        self.ent = ent()
        self.file_store = aasx.DictSupplementaryFileContainer()
        self.used_ids = set()

    def replace_str(self, str_input: str) -> str:
        dict_replace = {
            'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
            '°C': 'degreeCelsius',
            ' ': '_', '-': '_', '.': '', '/': '', '#': '', 
            '%': 'percentage', ',': '', '(': '', ')': '', '[': '', ']': ''
        }
        result = str_input
        for word, replacement in dict_replace.items():
            result = result.replace(word, replacement)
        return result

    def check_id_short(self, id_short: str):
        if id_short[0].isalpha():
            id_short = self.replace_str(id_short)
        else:
            id_short = f'X{id_short}'
        id_short = f'{re.sub(r"[^A-Za-z0-9_]", "_", id_short)}'
        return id_short

    def get_unique_id(self, base_id: str, local_context=None, context_suffix: Optional[str] = None) -> str:
        clean_id = self.check_id_short(base_id)
        if not clean_id:
            clean_id = "Component"
        common_props = ['Type', 'Level', 'Product_ID', 'Source_File', 'Volume', 'Surface_Area']
        if clean_id in common_props:
            return clean_id
        unique_id = clean_id
        if unique_id in self.used_ids and context_suffix:
            suffix_clean = self.check_id_short(str(context_suffix))
            candidate = f"{clean_id}_{suffix_clean}"
            if candidate not in self.used_ids:
                unique_id = candidate
        counter = 1
        while unique_id in self.used_ids:
            unique_id = f"{clean_id}_{counter}"
            counter += 1
        self.used_ids.add(unique_id)
        return unique_id
        
    def create_property(self, id_short: str, value_type, value, semantic_id):
        unique_id = self.get_unique_id(id_short)
        return self.ent.create_Prop(unique_id, value_type, value, None, None, semantic_id)
        
    def create_smc(self, id_short: str, value, semantic_id=None, context_suffix: Optional[str] = None):
        unique_id = self.get_unique_id(id_short, context_suffix=context_suffix)
        return self.ent.create_SMC(unique_id, value, None, None, semantic_id)
    
    def create_component_elements(self, component: ComponentNode, level: int = 0) -> List:
        elements = []
        elements.append(self.create_property('Product_ID', model.datatypes.String, component.product_id, self.map_eclass.get_IrdiCC_descr('Product_ID')[0]))
        elements.append(self.create_property('Type', model.datatypes.String, component.node_type, self.map_eclass.get_IrdiCC_descr('Type')[0]))
        elements.append(self.create_property('Level', model.datatypes.Int, level, self.map_eclass.get_IrdiCC_descr('Level')[0]))
        elements.append(self.create_property('Source_File', model.datatypes.String, os.path.basename(component.source_file), self.map_eclass.get_IrdiCC_descr('Source_File')[0]))
        if component.product_id in self.parser.standard_parts:
            standard_info = self.parser.standard_parts[component.product_id]
            elements.append(self.create_property('Standard_Type', model.datatypes.String, standard_info['type'], self.map_eclass.get_IrdiCC_descr('Standard_Type')[0]))
        if component.annotations:
            ann_elements = []
            for ann in component.annotations:
                if ann['name'] and ann['description']:
                    ann_prop = self.create_property(f"{ann['name']}", model.datatypes.String, ann['description'], self.map_eclass.get_IrdiCC_descr(f"{ann['name']}")[0])
                    ann_elements.append(ann_prop)
            if ann_elements:
                annotations_smc = self.create_smc('Annotations', tuple(ann_elements), self.map_eclass.get_IrdiCC_descr('Annotations')[0], context_suffix=component.product_id)
                elements.append(annotations_smc)
        file_elements = []
        # Prefer annotation STEP files; ensure at least one file per component
        for idx, filename in enumerate(component.annotation_files):
            if os.path.exists(filename):
                mime_type = "application/step"
                file_name = os.path.basename(filename)
                file_base, file_ext = os.path.splitext(file_name)
                safe_name = self.replace_str(file_base)
                file_path = f"/aasx/stp/annotations/{safe_name}{file_ext}"
                file_elements.append(self.ent.create_File(self.file_store, filename, file_path, f"AnnotationFile_{idx}", mime_type, None, None))
        if file_elements:
            elements.append(self.create_smc('Files', tuple(file_elements), self.map_eclass.get_IrdiCC_descr('Files')[0], context_suffix=component.product_id))
        if level == 0 and component.geometry_info:
            geom = component.geometry_info
            geom_elements = []
            if 'volume' in geom and geom['volume'] > 0:
                geom_elements.append(self.create_property('Volume', model.datatypes.Float, geom['volume'], self.map_eclass.get_IrdiCC_descr('Volume')[0]))
            if 'surface_area' in geom and geom['surface_area'] > 0:
                geom_elements.append(self.create_property('Surface_Area', model.datatypes.Float, geom['surface_area'], self.map_eclass.get_IrdiCC_descr('Surface_Area')[0]))
            if 'center_of_mass' in geom:
                com = geom['center_of_mass']
                semantic_id_center_of_mass = self.map_eclass.get_IrdiCC_descr('Center of mass')[0]
                com_smc = self.create_smc('Center_of_Mass', (
                    self.create_property('X', model.datatypes.Float, com[0], semantic_id_center_of_mass),
                    self.create_property('Y', model.datatypes.Float, com[1], semantic_id_center_of_mass),
                    self.create_property('Z', model.datatypes.Float, com[2], semantic_id_center_of_mass)
                ), semantic_id_center_of_mass)
                geom_elements.append(com_smc)
            if 'bounding_box' in geom:
                bbox = geom['bounding_box']
                semantic_bounding_box_min = self.map_eclass.get_IrdiCC_descr('Bounding_Box_Min')[0]
                semantic_bounding_box_max = self.map_eclass.get_IrdiCC_descr('Bounding_Box_Max')[0]
                semantic_bounding_box_range = self.map_eclass.get_IrdiCC_descr('Bounding_Box_Range')[0]
                semantic_bounding_box = self.map_eclass.get_IrdiCC_descr('Bounding_Box')[0]
                bbox_smc = self.create_smc('Bounding_Box', (
                    self.create_smc('Min', (
                        self.create_property('X', model.datatypes.Float, bbox['min'][0], semantic_bounding_box_min),
                        self.create_property('Y', model.datatypes.Float, bbox['min'][1], semantic_bounding_box_min),
                        self.create_property('Z', model.datatypes.Float, bbox['min'][2], semantic_bounding_box_min)
                    ), semantic_bounding_box_min),
                    self.create_smc('Max', (
                        self.create_property('X', model.datatypes.Float, bbox['max'][0], semantic_bounding_box_max),
                        self.create_property('Y', model.datatypes.Float, bbox['max'][1], semantic_bounding_box_max),
                        self.create_property('Z', model.datatypes.Float, bbox['max'][2], semantic_bounding_box_max)
                    ), semantic_bounding_box_max),
                    self.create_smc('Range', (
                        self.create_property('Length', model.datatypes.Float, bbox['range'][0], semantic_bounding_box_range),
                        self.create_property('Width', model.datatypes.Float, bbox['range'][1], semantic_bounding_box_range),
                        self.create_property('Height', model.datatypes.Float, bbox['range'][2], semantic_bounding_box_range)
                    ), semantic_bounding_box_range)
                ), semantic_bounding_box)
                geom_elements.append(bbox_smc)
            if geom_elements:
                geometry_smc = self.create_smc('Geometry', tuple(geom_elements), self.map_eclass.get_IrdiCC_descr('Geological_Measurement')[0])
                elements.append(geometry_smc)
        return elements
    
    def create_component_smc(self, component: ComponentNode, level: int = 0) -> model.SubmodelElementCollection:
        elements = self.create_component_elements(component, level)
        if component.children:
            child_elements = []
            for child in component.children:
                child_smc = self.create_component_smc(child, level + 1)
                child_elements.append(child_smc)
            children_smc = self.create_smc('Components', tuple(child_elements), self.map_eclass.get_IrdiCC_descr('Components')[0], context_suffix=component.product_id)
            elements.append(children_smc)
        # Ensure unique id_short for each component SMC, even for repeated identical components
        unique_name = self.get_unique_id(component.name, context_suffix=component.product_id)
        # Use a stable semantic class to avoid heavy fuzzy lookups for unique names
        semantic_component = self.map_eclass.get_IrdiCC_descr('Component')[0]
        return self.ent.create_SMC(unique_name, tuple(elements), None, None, semantic_component)

    def create_assembly_submodel(self):
        if not self.parser.assembly_tree:
            return None
        sm_assembly = model.Submodel(
            id_=model.Identifier('https://Assembly.com/ids/sm/AssemblyStructure'),
            id_short='AssemblyStructure'
        )
        root_elements = self.create_component_elements(self.parser.assembly_tree, 0)
        if self.parser.processed_files:
            main_file = self.parser.processed_files[0]
            file_info = self.parser.assembly_tree.file_info if hasattr(self.parser.assembly_tree, 'file_info') else {}
            main_info_elements = []
            main_info_elements.append(self.create_property('Main_Assembly_Name', model.datatypes.String,
                                   os.path.basename(main_file), self.map_eclass.get_IrdiCC_descr('Name')[0]))
            author = file_info.get('File_name', {}).get('author', '')
            if author:
                main_info_elements.append(self.create_property('Main_Assembly_Author', model.datatypes.String,
                                       author, self.map_eclass.get_IrdiCC_descr('Author')[0]))
            organization = file_info.get('File_name', {}).get('organization', '')
            if organization:
                main_info_elements.append(self.create_property('Main_Assembly_Organization', model.datatypes.String,
                                       organization, self.map_eclass.get_IrdiCC_descr('Organization')[0]))
            if main_info_elements:
                root_elements.extend(main_info_elements)
        if self.parser.assembly_tree.children:
            child_elements = []
            for child in self.parser.assembly_tree.children:
                child_smc = self.create_component_smc(child, 1)
                child_elements.append(child_smc)
            children_smc = self.create_smc('Components', tuple(child_elements), self.map_eclass.get_IrdiCC_descr('Components')[0], context_suffix=self.parser.assembly_tree.product_id)
            root_elements.append(children_smc)
        main_assembly_smc = self.create_smc('Main_Assembly', tuple(root_elements), self.map_eclass.get_IrdiCC_descr('Main_Assembly')[0], context_suffix=self.parser.assembly_tree.product_id)
        sm_assembly.submodel_element.add(main_assembly_smc)
        return sm_assembly
    
    def create_aas(self):
        root_name = "SSI_Anlage"
        obj_store, asset_info = self.ent.create_asset_information_rand_iri(
            model.DictObjectStore(), 
            root_name, 
            'I'
        )
        obj_store, id_aas, aas = self.ent.create_aas_rand_iri(
            obj_store, 
            root_name,
            root_name, 
            asset_info, 
            None
        )
        submodels = []
        sm_assembly = self.create_assembly_submodel()
        if sm_assembly:
            submodels.append(sm_assembly)
        for sm in submodels:
            aas.submodel.add(model.ModelReference.from_referable(sm))
            obj_store.add(sm)
        object_list = [aas] + submodels
        object_store = model.DictObjectStore(object_list)
        self.ent.write_aas(self.output_filename, id_aas, object_store, self.file_store)
        print(f"Unified AAS saved to: {self.output_filename}")


