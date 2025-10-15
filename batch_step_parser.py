import os
import re
import glob
from typing import List, Optional
from collections import defaultdict

from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Extend.TopologyUtils import TopologyExplorer


class ComponentNode:
    """Represents a component (part or sub-assembly) with its annotations"""
    def __init__(self, name: str, product_id: str, source_file: str, node_type: str = "PART"):
        self.name = name
        self.product_id = product_id
        self.source_file = source_file
        self.node_type = node_type  # ASSEMBLY, PART, STANDARD_PART
        self.children = []
        self.parent = None
        self.annotations = []
        self.geometry_info = {}
        self.file_info = {}
        self.original_product_id = product_id  # Keep track of original ID for matching
        self.annotation_files = []
        
    def add_child(self, child):
        child.parent = self
        self.children.append(child)
        
    def is_leaf(self):
        return len(self.children) == 0


class BatchStepParser:
    """Parser for multiple STEP files with components and annotations"""
    
    def __init__(self, input_directory: str, main_assembly_file: str = None):
        self.input_directory = input_directory
        self.main_assembly_file = main_assembly_file
        self.tolerance = 1e-5
        self.enable_annotation_fallback = False  # speeds up large runs
        self.extract_root_geometry = False  # disable heavy geometry by default
        
        # Global data structures
        self.all_components = {}  # component_id -> ComponentNode
        self.all_annotations = {}  # kept for compatibility, no longer populated
        self.component_annotations = defaultdict(list)  # kept for compatibility, no longer populated
        self.standard_parts = {}  # component_id -> standard_part_info
        self.assembly_relationships = []  # parent-child relationships
        
        # File tracking
        self.processed_files = []
        self.annotation_files = []  # Files that only provide annotations
        
        # Assembly structure
        self.assembly_tree = None
        self.component_name_index = {}  # normalized_name -> ComponentNode

        # Precompile regex patterns for performance
        self.re_file_description = re.compile(r'FILE_DESCRIPTION\s*\(\s*(.*?)\s*\)\s*;', re.DOTALL)
        self.re_file_name = re.compile(r'FILE_NAME\s*\(\s*(.*?)\s*\)\s*;', re.DOTALL)
        self.re_file_schema = re.compile(r'FILE_SCHEMA\s*\(\s*(.*?)\s*\)\s*;', re.DOTALL)
        self.re_quoted = re.compile(r"[\'\"](.*?)[\'\"]")
        self.re_product = re.compile(r'#(\d+)\s*=\s*PRODUCT\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"].*?\)\s*;', re.DOTALL)
        self.re_annotation = re.compile(r'#(\d+)\s*=\s*DESCRIPTIVE_REPRESENTATION_ITEM\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"].*?\)\s*;', re.DOTALL)
        self.re_repr = re.compile(r'#(\d+)\s*=\s*REPRESENTATION\s*\(\s*[\'\"](.*?)[\'\"],\s*\((.*?)\),\s*#(\d+)\)\s*;', re.DOTALL)
        self.re_prop_def_repr = re.compile(r'#(\d+)\s*=\s*PROPERTY_DEFINITION_REPRESENTATION\s*\(\s*#(\d+),\s*#(\d+)\)\s*;', re.DOTALL)
        self.re_prop_def = re.compile(r'#(\d+)\s*=\s*PROPERTY_DEFINITION\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+)\)\s*;', re.DOTALL)
        self.re_prod_def = re.compile(r'#(\d+)\s*=\s*PRODUCT_DEFINITION\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+),\s*#(\d+)\)\s*;', re.DOTALL)
        self.re_formation = re.compile(r'#(\d+)\s*=\s*PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+),.*?\)\s*;', re.DOTALL)
        self.re_usage = re.compile(r'#(\d+)\s*=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+),\s*#(\d+),.*?\)\s*;', re.DOTALL)

    def find_step_files(self) -> List[str]:
        step_files = set()
        for ext in ['*.stp', '*.step', '*.STP', '*.STEP']:
            step_files.update(glob.glob(os.path.join(self.input_directory, ext)))
            step_files.update(glob.glob(os.path.join(self.input_directory, "**", ext), recursive=True))
        unique_files = []
        seen_paths = set()
        for file_path in step_files:
            abs_path = os.path.abspath(file_path)
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                unique_files.append(file_path)
        return unique_files

    def load_file_content(self, filename: str) -> str:
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return ""

    def extract_file_info(self, content: str) -> dict:
        file_info = {
            'File_description': {'Description': '', 'Implementation_level': ''},
            'File_name': {'name': '', 'time_stamp': '', 'author': '', 'organization': '',
                         'preprocessor_version': '', 'originating_system': '', 'authorisation': ''},
            'File_schema': ''
        }
        file_description = self.re_file_description.findall(content)
        if file_description:
            desc_parts = self.re_quoted.findall(file_description[0])
            if len(desc_parts) >= 2:
                file_info['File_description']['Description'] = desc_parts[0].strip()
                file_info['File_description']['Implementation_level'] = desc_parts[1].strip()
        file_name_match = self.re_file_name.findall(content)
        if file_name_match:
            name_parts = self.re_quoted.findall(file_name_match[0])
            if len(name_parts) >= 7:
                file_info['File_name']['name'] = name_parts[0].strip()
                file_info['File_name']['time_stamp'] = name_parts[1].strip()
                file_info['File_name']['author'] = name_parts[2].strip()
                file_info['File_name']['organization'] = name_parts[3].strip()
                file_info['File_name']['preprocessor_version'] = name_parts[4].strip()
                file_info['File_name']['originating_system'] = name_parts[5].strip()
                file_info['File_name']['authorisation'] = name_parts[6].strip()
        file_schema = self.re_file_schema.findall(content)
        if file_schema:
            schema_parts = self.re_quoted.findall(file_schema[0])
            if schema_parts:
                file_info['File_schema'] = schema_parts[0].strip()
        return file_info

    def extract_products_from_content(self, content: str) -> dict:
        products = {}
        matches = self.re_product.findall(content)
        for product_id, product_name, product_desc in matches:
            products[product_id] = {
                'name': product_name.strip(),
                'description': product_desc.strip(),
                'id': product_id
            }
        return products

    def extract_annotations_from_content(self, content: str) -> dict:
        annotations = {}
        matches = self.re_annotation.findall(content)
        for annotation_id, name, description in matches:
            annotations[annotation_id] = {
                'name': name.strip(),
                'description': description.strip()
            }
        return annotations

    def link_annotations_to_products_in_content(self, content: str, products: dict, annotations: dict) -> dict:
        product_annotations = defaultdict(list)
        representations = self.re_repr.findall(content)
        prop_def_reprs = self.re_prop_def_repr.findall(content)
        prop_defs = self.re_prop_def.findall(content)
        prod_defs = self.re_prod_def.findall(content)
        formations = self.re_formation.findall(content)
        repr_to_annotations = {}
        repr_to_product = {}
        for repr_id, repr_name, items_str, context_id in representations:
            item_refs = re.findall(r'#(\d+)', items_str)
            annotations_in_repr = [item_id for item_id in item_refs if item_id in annotations]
            if annotations_in_repr:
                repr_to_annotations[repr_id] = annotations_in_repr
        prod_def_to_formation = {prod_def_id: formation_ref for prod_def_id, _, _, formation_ref, _ in prod_defs}
        formation_to_product = {formation_id: product_ref for formation_id, _, _, product_ref in formations}
        prop_def_to_prod_def = {prop_def_id: prod_def_ref for prop_def_id, _, _, prod_def_ref in prop_defs}
        for _pdr_id, prop_def_ref, repr_ref in prop_def_reprs:
            if repr_ref in repr_to_annotations and prop_def_ref in prop_def_to_prod_def:
                prod_def_id = prop_def_to_prod_def[prop_def_ref]
                if prod_def_id in prod_def_to_formation:
                    formation_id = prod_def_to_formation[prod_def_id]
                    if formation_id in formation_to_product:
                        product_id = formation_to_product[formation_id]
                        if product_id in products:
                            repr_to_product[repr_ref] = product_id
        for repr_id, annotation_ids in repr_to_annotations.items():
            if repr_id in repr_to_product:
                product_id = repr_to_product[repr_id]
                for ann_id in annotation_ids:
                    if ann_id in annotations:
                        product_annotations[product_id].append(annotations[ann_id])
        if self.enable_annotation_fallback:
            for product_id, product_info in products.items():
                product_name_lower = product_info['name'].lower()
                for _ann_id, annotation in annotations.items():
                    ann_name_lower = annotation['name'].lower()
                    ann_desc_lower = annotation['description'].lower()
                    if (product_name_lower in ann_name_lower or 
                        product_name_lower in ann_desc_lower or
                        ann_name_lower in product_name_lower):
                        if annotation not in product_annotations[product_id]:
                            product_annotations[product_id].append(annotation)
        return dict(product_annotations)

    def extract_assembly_relationships_from_content(self, content: str, products: dict):
        usages = self.re_usage.findall(content)
        prod_def_pattern = r'#(\d+)\s*=\s*PRODUCT_DEFINITION\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+),\s*#(\d+)\)\s*;'
        prod_defs = re.findall(prod_def_pattern, content, re.DOTALL)
        formation_pattern = r'#(\d+)\s*=\s*PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE\s*\(\s*[\'\"](.*?)[\'\"],\s*[\'\"](.*?)[\'\"],\s*#(\d+),.*?\)\s*;'
        formations = re.findall(formation_pattern, content, re.DOTALL)
        prod_def_to_formation = {prod_def_id: formation_ref for prod_def_id, _, _, formation_ref, _ in prod_defs}
        formation_to_product = {formation_id: product_ref for formation_id, _, _, product_ref in formations}
        def resolve_product_from_definition(prod_def_id: str) -> Optional[str]:
            if prod_def_id in prod_def_to_formation:
                formation_ref = prod_def_to_formation[prod_def_id]
                if formation_ref in formation_to_product:
                    product_ref = formation_to_product[formation_ref]
                    return product_ref if product_ref in products else None
            return None
        for _usage_id, _usage_name, _usage_desc, relating_prod_def, related_prod_def in usages:
            parent_product_id = resolve_product_from_definition(relating_prod_def)
            child_product_id = resolve_product_from_definition(related_prod_def)
            if parent_product_id and child_product_id:
                self.assembly_relationships.append({
                    'parent_product_id': parent_product_id,
                    'child_product_id': child_product_id,
                    'parent_product_name': products[parent_product_id]['name'],
                    'child_product_name': products[child_product_id]['name']
                })

    def identify_component_type(self, product_info: dict, annotations: list, has_children: bool = False) -> str:
        standard_keywords = [
            'screw', 'bolt', 'nut', 'washer', 'bearing', 'motor', 'sensor',
            'valve', 'cylinder', 'spring', 'pin', 'gear', 'coupling',
            'fastener', 'fitting', 'connector', 'switch', 'relay',
            'actuator', 'encoder', 'drive', 'pump', 'filter'
        ]
        product_text = f"{product_info['name']} {product_info['description']}".lower()
        annotation_text = " ".join([f"{ann['name']} {ann['description']}" for ann in annotations]).lower()
        combined_text = f"{product_text} {annotation_text}"
        for keyword in standard_keywords:
            if keyword in combined_text:
                return "STANDARD_PART"
        manufacturer_patterns = [
            r'(?i)(festo|balluff|hbm|siemens|bosch|parker|smc|omron|keyence|sick|ifm)',
            r'[A-Z]{2,}-\d+',
            r'\b[A-Z]\d{4,}\b',
        ]
        for pattern in manufacturer_patterns:
            if re.search(pattern, combined_text):
                return "STANDARD_PART"
        return "ASSEMBLY" if has_children else "PART"

    def process_main_assembly(self, main_path: str):
        print(f"Processing main assembly: {os.path.basename(main_path)}")
        content = self.load_file_content(main_path)
        if not content:
            return False
        products = self.extract_products_from_content(content)
        annotations = self.extract_annotations_from_content(content)
        file_info = self.extract_file_info(content)
        product_annotations = self.link_annotations_to_products_in_content(content, products, annotations)
        print(f"  Found {len(products)} products, {len(annotations)} annotations")
        annotated_count = sum(1 for _pid, anns in product_annotations.items() if anns)
        if annotated_count:
            print(f"  Products with annotations: {annotated_count}")
        self.extract_assembly_relationships_from_content(content, products)
        print(f"  Found {len(self.assembly_relationships)} assembly relationships")
        for index, (product_id, product_info) in enumerate(products.items(), start=1):
            has_children = any(rel['parent_product_id'] == product_id for rel in self.assembly_relationships)
            component_annotations = product_annotations.get(product_id, [])
            if has_children:
                node_type = "ASSEMBLY"
            else:
                node_type = self.identify_component_type(product_info, component_annotations, has_children)
            component = ComponentNode(
                name=product_info['name'],
                product_id=f"P{index:05d}",
                source_file=main_path,
                node_type=node_type
            )
            component.original_product_id = product_id
            component.annotations = component_annotations.copy()
            component.file_info = file_info
            self.all_components[component.product_id] = component
            for ann in component_annotations:
                ann_id = f"{component.product_id}_ann_{len(self.all_annotations)}"
                self.all_annotations[ann_id] = ann
                self.component_annotations[component.product_id].append(ann)
            if node_type == "STANDARD_PART":
                self.standard_parts[component.product_id] = {
                    'type': 'STANDARD_PART',
                    'name': product_info['name'],
                    'description': product_info['description']
                }
            if component_annotations:
                print(f"  Created component '{product_info['name']}' with {len(component_annotations)} annotations")
        self.processed_files.append(main_path)
        # Build fast lookup index for component name matching
        def remove_solidworks_suffix(name: str) -> str:
            return re.sub(r'-\d+$', '', name.strip())
        self.component_name_index = {}
        for comp in self.all_components.values():
            key = remove_solidworks_suffix(comp.name).upper()
            # Keep first occurrence; others will be reachable via product_id uniqueness
            if key not in self.component_name_index:
                self.component_name_index[key] = comp
        print(f"  Created {len(products)} components from main assembly")
        return True

    def supplement_annotations_from_files(self, step_files: List[str]):
        main_path = os.path.join(self.input_directory, self.main_assembly_file) if self.main_assembly_file else None
        def remove_solidworks_suffix(name):
            return re.sub(r'-\d+$', '', name.strip())
        for filename in step_files:
            if main_path and os.path.abspath(filename) == os.path.abspath(main_path):
                continue
            print(f"Supplementing annotations from: {os.path.basename(filename)}")
            content = self.load_file_content(filename)
            if not content:
                continue
            # Fast pre-scan: skip files with no annotation token
            if 'DESCRIPTIVE_REPRESENTATION_ITEM' not in content and 'PROPERTY_DEFINITION_REPRESENTATION' not in content:
                # No annotations present, skip early
                continue
            products = self.extract_products_from_content(content)
            annotations = self.extract_annotations_from_content(content)
            product_annotations = self.link_annotations_to_products_in_content(content, products, annotations)
            if not annotations:
                print(f"  No annotations found")
                continue
            print(f"  Found {len(annotations)} annotations in file")
            all_file_annotations = []
            for _product_id, product_anns in product_annotations.items():
                all_file_annotations.extend(product_anns)
            if not all_file_annotations:
                print(f"  No annotations linked to products")
                continue
            print(f"  Total {len(all_file_annotations)} annotations to be assigned")
            file_base_name = os.path.splitext(os.path.basename(filename))[0]
            file_base_clean = remove_solidworks_suffix(file_base_name)
            # Match only by cleaned filename to component name
            matching_component = None
            key = file_base_clean.upper()
            if key in self.component_name_index:
                candidate = self.component_name_index[key]
                if candidate != self.assembly_tree:
                    matching_component = candidate
                    print(f"  Matched '{file_base_name}' → '{candidate.name}'")
            if matching_component:
                original_ann_count = len(matching_component.annotations)
                new_annotations = []
                for ann in all_file_annotations:
                    if not any(existing_ann['name'] == ann['name'] and existing_ann['description'] == ann['description'] 
                               for existing_ann in matching_component.annotations):
                        matching_component.annotations.append(ann)
                        new_annotations.append(ann)
                        ann_id = f"{matching_component.product_id}_file_{len(self.all_annotations)}"
                        self.all_annotations[ann_id] = ann
                        self.component_annotations[matching_component.product_id].append(ann)
                print(f"  Added {len(new_annotations)} new annotations to '{matching_component.name}' (had {original_ann_count} before)")
                if filename not in matching_component.annotation_files:
                    matching_component.annotation_files.append(filename)
            else:
                print(f"  No matching component found for '{file_base_name}' (cleaned: '{file_base_clean}')")
                available_components = [remove_solidworks_suffix(comp.name) for comp in self.all_components.values() if comp != self.assembly_tree]
                print(f"  Available components (cleaned): {available_components}")
            self.annotation_files.append(filename)

    def build_assembly_tree(self):
        if not self.assembly_relationships:
            self.assembly_tree = ComponentNode("SSI_Anlage_Root", "root_assembly", "virtual", "ASSEMBLY")
            for component in self.all_components.values():
                self.assembly_tree.add_child(component)
            return
        parent_components = set()
        child_components = set()
        for rel in self.assembly_relationships:
            parent_orig_id = rel['parent_product_id']
            child_orig_id = rel['child_product_id']
            parent_comp = None
            child_comp = None
            for comp in self.all_components.values():
                if comp.original_product_id == parent_orig_id:
                    parent_comp = comp
                if comp.original_product_id == child_orig_id:
                    child_comp = comp
            if parent_comp and child_comp:
                parent_comp.add_child(child_comp)
                parent_components.add(parent_comp.product_id)
                child_components.add(child_comp.product_id)
        root_candidates = [comp for comp_id, comp in self.all_components.items() 
                          if comp_id in parent_components and comp_id not in child_components]
        if root_candidates:
            self.assembly_tree = root_candidates[0]
        else:
            self.assembly_tree = ComponentNode("SSI_Anlage_Root", "root_assembly", "virtual", "ASSEMBLY")
            orphaned = [comp for comp_id, comp in self.all_components.items() 
                       if comp_id not in child_components]
            for comp in orphaned:
                self.assembly_tree.add_child(comp)

    def extract_geometry_info_for_component(self, component: ComponentNode):
        if not os.path.exists(component.source_file) or component.source_file == "virtual":
            return
        try:
            step_reader = STEPControl_Reader()
            step_reader.ReadFile(component.source_file)
            step_reader.TransferRoot()
            shape = step_reader.Shape()
            if shape.IsNull():
                return
            props = GProp_GProps()
            brepgprop.VolumeProperties(shape, props)
            volume = props.Mass()
            t = TopologyExplorer(shape)
            surface_area = 0
            for face in t.faces():
                brepgprop.SurfaceProperties(face, props, self.tolerance)
                surface_area += props.Mass()
            cog = props.CentreOfMass()
            center_of_mass = [cog.X(), cog.Y(), cog.Z()]
            bbox = Bnd_Box()
            bbox.SetGap(self.tolerance)
            brepbndlib.Add(shape, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
            component.geometry_info = {
                'volume': volume,
                'surface_area': surface_area,
                'center_of_mass': center_of_mass,
                'bounding_box': {
                    'min': [xmin, ymin, zmin],
                    'max': [xmax, ymax, zmax],
                    'range': [xmax-xmin, ymax-ymin, zmax-zmin]
                }
            }
        except Exception as e:
            print(f"Error extracting geometry for {component.name}: {e}")

    def parse_batch(self):
        print(f"Starting batch processing in: {self.input_directory}")
        step_files = self.find_step_files()
        if not step_files:
            print("No STEP files found!")
            return False
        print(f"Found {len(step_files)} STEP files")
        success = False
        if self.main_assembly_file:
            main_path = os.path.join(self.input_directory, self.main_assembly_file)
            if os.path.exists(main_path):
                success = self.process_main_assembly(main_path)
                if success:
                    self.supplement_annotations_from_files(step_files)
            else:
                print(f"Main assembly file not found: {main_path}")
        if not success:
            print("Main assembly processing failed, using fallback method")
            return False
        print("Building assembly hierarchy...")
        self.build_assembly_tree()
        if self.extract_root_geometry and self.assembly_tree and self.assembly_tree.source_file != "virtual":
            print("Extracting geometry information (root)...")
            self.extract_geometry_info_for_component(self.assembly_tree)
        print(f"\nBatch processing complete:")
        print(f"- Main assembly processed: 1")
        print(f"- Annotation files processed: {len(self.annotation_files)}")
        print(f"- Total components: {len(self.all_components)}")
        print(f"- Total parts (leaf components): {sum(1 for comp in self.all_components.values() if len(comp.children) == 0)}")
        print(f"- Total annotations: {sum(len(comp.annotations) for comp in self.all_components.values())}")
        print(f"- Standard parts: {len(self.standard_parts)}")
        print(f"- Assembly relationships: {len(self.assembly_relationships)}")
        print(f"- Assembly tree root: {self.assembly_tree.name if self.assembly_tree else 'None'}")
        return True


