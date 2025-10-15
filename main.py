#!/usr/bin/env python 3.10.15
"""
Batch Assembly STEP to AAS Conversion Script (entrypoint)

This script wires together the parser and AAS builder. The implementation
of parsing and AAS construction now lives in separate modules:
- batch_step_parser.py: ComponentNode, BatchStepParser
- batch_aas_from_stp.py: BatchAASFromSTP
"""

import os
import argparse

from batch_step_parser import BatchStepParser
from batch_aas_from_stp import BatchAASFromSTP


def main():
    """Main execution function for batch processing"""
    parser = argparse.ArgumentParser(description='Batch STEP to AAS Converter')
    parser.add_argument('input_directory', help='Directory containing STEP files')
    parser.add_argument('-m', '--main-assembly', help='Main assembly file name (required for proper processing)')
    parser.add_argument('-o', '--output', help='Output AAS filename (optional)')

    args = parser.parse_args()

    input_directory = args.input_directory
    main_assembly_file = args.main_assembly
    output_filename = args.output

    # Check if input directory exists
    if not os.path.exists(input_directory):
        print(f"Error: Directory not found: {input_directory}")
        return

    # Check if main assembly file is specified
    if not main_assembly_file:
        print("Error: Main assembly file must be specified with -m option")
        print("Example: python fixed_batch_converter.py input_dir -m main_assembly.stp")
        return

    # Set default output filename
    if not output_filename:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_filename = os.path.join(output_dir, "unified_assembly.aasx")

    try:
        print(f"\n{'='*60}")
        print(f"Batch Processing STEP Files")
        print(f"Input Directory: {input_directory}")
        print(f"Main Assembly: {main_assembly_file}")
        print(f"{'='*60}")

        # Parse batch of STEP files
        batch_parser = BatchStepParser(input_directory, main_assembly_file)
        # Restore original behavior: extract geometry for the root assembly
        batch_parser.extract_root_geometry = True
        success = batch_parser.parse_batch()

        if not success:
            print("Batch parsing failed!")
            return

        # Create unified AAS
        aas_converter = BatchAASFromSTP(batch_parser, output_filename)
        aas_converter.create_aas()

        print(f"\n{'='*60}")
        print(f"Batch conversion completed successfully!")
        print(f"Output: {output_filename}")
        print(f"{'='*60}")

        # Print detailed summary
        if batch_parser.assembly_tree:
            print(f"\nAssembly Summary:")
            print(f"- Root Assembly: {batch_parser.assembly_tree.name}")
            print(f"- Main Assembly File: {os.path.basename(batch_parser.processed_files[0]) if batch_parser.processed_files else 'None'}")
            print(f"- Annotation Files: {len(batch_parser.annotation_files)}")
            print(f"- Total Components: {len(batch_parser.all_components)}")
            print(f"- Total Parts (leaf components): {sum(1 for comp in batch_parser.all_components.values() if len(comp.children) == 0)}")
            print(f"- Components with Annotations: {sum(1 for comp in batch_parser.all_components.values() if comp.annotations)}")
            print(f"- Total Annotations: {sum(len(comp.annotations) for comp in batch_parser.all_components.values())}")
            print(f"- Standard Parts: {len(batch_parser.standard_parts)}")
            print(f"- Assembly Relationships: {len(batch_parser.assembly_relationships)}")

            # Show hierarchy
            def print_hierarchy(node, level=0):
                indent = "  " * level
                ann_count = len(node.annotations)
                print(f"{indent}- {node.name} ({node.node_type}) [Level {level}] {ann_count} annotations")
                for child in node.children:
                    print_hierarchy(child, level + 1)

            print(f"\nAssembly Hierarchy:")
            print_hierarchy(batch_parser.assembly_tree)

    except Exception as e:
        print(f"Error during batch processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()