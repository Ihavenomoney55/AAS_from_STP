from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.util.identification import *
from basyx.aas.model import LangStringSet

class ent:
    def __init__(self):
        pass

    def get_kind(self, kind):
        if kind == 'I':
            return model.ModellingKind.INSTANCE
        elif kind == 'T':
            return model.ModellingKind.TEMPLATE
        return None

    def get_kind_asset(self, kind):
        if kind == 'I':
            return model.AssetKind.INSTANCE
        elif kind == 'T':
            return model.AssetKind.TYPE
        return None

    def create_iri(self, obj_store, id_http, type_):
        generator = NamespaceIRIGenerator(id_http, obj_store)
        id_ = generator.generate_id()
        if type_ == 'submodel':
            obj_store.add(model.Submodel(id_))
        return obj_store, id_

    def create_aas(self, id_short, id_aas, asset, derived_from):
        aas = model.AssetAdministrationShell(
            id_short=id_short,
            id_=id_aas,
            asset_information=asset,
            derived_from=derived_from
        )
        return id_aas, aas

    def create_aas_rand_iri(self, obj_store, id_short, aas_name, asset, derived_from):
        obj_store, id_aas = self.create_iri(obj_store, 'https://' + aas_name + '.com/ids/aas/', 'aas')
        id_aas, aas = self.create_aas(id_short, id_aas, asset, derived_from)
        obj_store.add(aas)
        return obj_store, id_aas, aas

    def create_asset_information(self, id_):
        return model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id=model.Identifier(id_)
        )

    def create_asset_information_rand_iri(self, obj_store, asset_name, kind):
        obj_store, id_asset = self.create_iri(obj_store, 'https://' + asset_name + '.com/ids/asset/', 'asset')
        asset_information = self.create_asset_information(id_asset)
        return obj_store, asset_information

    def create_SM(self, id_SM, submodel_elements, id_short, semantic_id, kind):
        SM = model.Submodel(
            id_=id_SM,
            submodel_element=submodel_elements,
            id_short=id_short,
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
            kind=self.get_kind(kind)
        )
        return SM
    
    def create_SM_rand_iri(self, obj_store, id_short, SM_name, submodel_elements, semantic_id, kind):
        obj_store, id_SM = self.create_iri(obj_store, 'https://' + SM_name + '.com/ids/sm/', 'submodel')
        SM = self.create_SM(id_SM, submodel_elements, id_short, semantic_id, kind)
        return obj_store, SM

    def create_SMC(self, id_short, value, category, description, semantic_id):
        SMC = model.SubmodelElementCollection(
            id_short=id_short,
            value=value,
            category=category,
            description=self.create_description(description),  # Ensure description is added
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ])
        )
        return SMC

    def create_Prop(self, id_short, value_type, value, category, description, semantic_id):
        Prop = model.Property(
            id_short=id_short,
            value_type=value_type,
            value=value,
            category=category,
            description=self.create_description(description),
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
        )
        return Prop

    def create_Cap(self, id_short, category, description, semantic_id):
        Cap = model.Capability(
            id_short=id_short,
            category=category,
            description=self.create_description(description),
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
        )
        return Cap

    def create_Range(self, id_short, value_type, min, max, category, description, semantic_id):
        Range = model.Range(
            id_short=id_short,
            value_type=value_type,
            min=min,
            max=max,
            category=category,
            description=self.create_description(description),
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
        )
        return Range

    def create_File(self, file_store, file_path, aasx_file_path, id_short, mime_type, description, category):
        with open(file_path, 'rb') as f:
            actual_file_name = file_store.add_file(aasx_file_path, f, mime_type)
        File = model.File(
            id_short=id_short,
            content_type=mime_type,
            category=category,
            value=actual_file_name,
            description=self.create_description(description),
        )
        return File


    def create_Rel(self, id_short, description, first_value_keys, second_value_keys, category):
        Rel = model.RelationshipElement(
            id_short=id_short,
            description=self.create_description(description),
            first=model.ModelReference(
                type_=model.KeyTypes.SUBMODEL_ELEMENT,
                key=first_value_keys
            ),
            second=model.ModelReference(
                type_=model.KeyTypes.SUBMODEL_ELEMENT,
                key=second_value_keys 
            ),
            category=category,
        )
        return Rel


    def create_Ent(self, id_short, description, category, ent_type, statement, semantic_id, global_asset_id):
        Ent = model.Entity(
            id_short=id_short,
            description=self.create_description(description),
            category=category,
            entity_type=ent_type,
            statement=statement,
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
            global_asset_id=global_asset_id,
        )
        return Ent

    def create_Ref(self, id_short, value, category, description, semantic_id):
        Ref = model.ReferenceElement(
            id_short=id_short,
            value=value,
            category=category,
            description=self.create_description(description),
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
        )
        return Ref

    def create_Opr(self, id_short, category, description, semantic_id):
        Ref = model.Operation(
            id_short=id_short,
            category=category,
            description=self.create_description(description),
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=semantic_id)
            ]),
        )
        return Ref

    def create_obj_store(self, aas, asset, submodels):
        # Initialize object list with only AAS and submodels
        object_list = [aas]

        # Iterate through each submodel
        for sm in submodels:
            # Convert each submodel to a model reference and add to the AAS submodel collection
            aas.submodel.add(model.ModelReference.from_referable(sm))
            # Add the submodel to the object list
            object_list.append(sm)

        # Create the object store
        object_store = model.DictObjectStore(object_list)
        return object_store

    def write_aas(self, outfile, id_aas, object_store, file_store):
        with aasx.AASXWriter(outfile) as writer:
            print("Writing AASX file with the following descriptions:")
            for obj in object_store:
                if hasattr(obj, 'description'):
                    print(f"{obj.id_short}: {obj.description}")
            writer.write_aas(
                aas_ids=id_aas,
                object_store=object_store,
                file_store=file_store
            )


    def create_description(self, description_text):
        """
        Convert a plain string description into a LangStringSet with default language 'en',
        and split it into multiple LangStringSet entries if it's too long.
        """
        max_length = 1023 

        if isinstance(description_text, str) and description_text.strip():
            if len(description_text) > max_length:
                print(f"Warning: Description too long ({len(description_text)} characters). Splitting into multiple parts.")
                parts = [description_text[i:i+max_length] for i in range(0, len(description_text), max_length)]
                lang_string_set = LangStringSet({'en': ' '.join(parts)})
            else:
                lang_string_set = LangStringSet({'en': description_text})
            return lang_string_set
        return None