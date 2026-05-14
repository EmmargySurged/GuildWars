import pandas as pd
import openpyxl
import json
import sys
import argparse
import os
import re
import csv


DEFAULT_TABLE_CRITERIA = ["name", "background", "class", "subclass"]
DEFAULT_TABLE_FORMATS = ["json"]
DEFAULT_JSON_PATHS = [
    "./Books/Guild Wars.json",
    "./Books/Guild Wars Prophecies.json",
    "./Books/Guild Wars Factions.json",
    "./Books/Guild Wars Nightfall.json",
    "./Books/Guild Wars Eye of the North.json",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Update Guild Wars spells with classes/subclasses and optionally export spell tables."
    )
    parser.add_argument(
        "--generate-tables",
        action="store_true",
        help="Generate per-book spell tables after updating class/subclass data.",
    )
    parser.add_argument(
        "--table-criteria",
        nargs="+",
        choices=DEFAULT_TABLE_CRITERIA,
        default=DEFAULT_TABLE_CRITERIA,
        help="Table criteria to generate.",
    )
    parser.add_argument(
        "--table-formats",
        nargs="+",
        choices=["json", "csv", "xlsx"],
        default=DEFAULT_TABLE_FORMATS,
        help="Output formats for generated tables.",
    )
    parser.add_argument(
        "--tables-output-dir",
        default=".\\Books\\Tables",
        help="Directory where per-book table output files are written.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--json-paths",
        nargs="+",
        default=None,
        help="Optional list of book JSON files to process. Defaults to built-in Guild Wars paths.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process files without writing updated spell JSON inputs.",
    )
    return parser.parse_args()


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def get_background_names(spell):
    backgrounds = spell.get("backgrounds", [])
    names = set()
    for background in backgrounds:
        if isinstance(background, dict):
            value = background.get("name", "").strip()
        else:
            value = str(background).strip()
        if value:
            names.add(value)
    return sorted(names, key=str.casefold)


def get_class_names(spell):
    classes_data = spell.get("classes", {})
    from_class_list = classes_data.get("fromClassList", [])
    names = set()
    for class_entry in from_class_list:
        value = class_entry.get("name", "").strip()
        if value:
            names.add(value)
    return sorted(names, key=str.casefold)


def get_subclass_names(spell):
    classes_data = spell.get("classes", {})
    from_subclass = classes_data.get("fromSubclass", [])
    names = set()
    for subclass_entry in from_subclass:
        subclass_data = subclass_entry.get("subclass", {})
        short_name = str(subclass_data.get("shortName", "")).strip()
        full_name = str(subclass_data.get("name", "")).strip()
        value = short_name if short_name else full_name
        if value:
            names.add(value)
    return sorted(names, key=str.casefold)


def build_table_rows(spells):
    rows = []
    for spell in sorted(spells, key=lambda s: str(s.get("name", "")).casefold()):
        spell_name = spell.get("name", "Unknown Spell")
        spell_source = spell.get("source", "UNK")
        rows.append([
            {
                "type": "statblock",
                "tag": "spell",
                "name": spell_name,
                "source": spell_source,
            }
        ])
    return rows


def build_table(table_name, table_source, spells):
    return {
        "type": "table",
        "name": table_name,
        "source": table_source,
        "rows": build_table_rows(spells),
    }


def generate_spell_tables(spells, criteria):
    tables = []

    if "name" in criteria:
        source = spells[0].get("source", "UNK") if spells else "UNK"
        tables.append(build_table("Spells [Name]", source, spells))

    grouping_specs = [
        ("background", get_background_names, "Background"),
        ("class", get_class_names, "Class"),
        ("subclass", get_subclass_names, "Subclass"),
    ]

    for criterion, extractor, label in grouping_specs:
        if criterion not in criteria:
            continue

        grouped_spells = {}
        for spell in spells:
            for group_name in extractor(spell):
                grouped_spells.setdefault(group_name, []).append(spell)

        for group_name in sorted(grouped_spells.keys(), key=str.casefold):
            table_source = grouped_spells[group_name][0].get("source", "UNK") if grouped_spells[group_name] else "UNK"
            table_name = f"Spells [{label}: {group_name}]"
            tables.append(build_table(table_name, table_source, grouped_spells[group_name]))

    return tables


def flatten_tables_for_tabular_export(tables):
    rows = []
    for table in tables:
        table_name = table.get("name", "")
        table_source = table.get("source", "UNK")

        criterion = "Unknown"
        group_name = "All"

        if table_name.startswith("Spells [") and table_name.endswith("]"):
            content = table_name[8:-1]
            if ": " in content:
                criterion, group_name = content.split(": ", 1)
            else:
                criterion = content

        for row in table.get("rows", []):
            if not row:
                continue
            cell = row[0]
            rows.append(
                {
                    "table_name": table_name,
                    "table_source": table_source,
                    "criterion": criterion,
                    "group": group_name,
                    "spell_name": cell.get("name", ""),
                    "spell_source": cell.get("source", ""),
                }
            )
    return rows


def is_program_generated_table(table):
    if not isinstance(table, dict):
        return False
    table_name = str(table.get("name", ""))
    return table_name.startswith("Spells [") and table_name.endswith("]")


def remove_generated_tables(data):
    if not isinstance(data, dict):
        return
    tables = data.get("table")
    if isinstance(tables, list):
        data["table"] = [table for table in tables if not is_program_generated_table(table)]


def add_generated_tables(data, tables):
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object.")
    if "table" not in data or not isinstance(data["table"], list):
        data["table"] = []
    data["table"].extend(tables)


def remove_old_table_exports(output_dir, base_name, verbose=True):
    if not os.path.isdir(output_dir):
        return

    export_prefix = f"{base_name} - Spell Tables"
    for file_name in os.listdir(output_dir):
        if not file_name.startswith(export_prefix):
            continue
        if not file_name.lower().endswith((".json", ".csv", ".xlsx")):
            continue

        file_path = os.path.join(output_dir, file_name)
        try:
            os.remove(file_path)
            if verbose:
                print(f"Deleted old table export: {file_path}")
        except FileNotFoundError:
            continue


def save_json_with_tables(json_path, data, dry_run=False, verbose=True):
    if dry_run:
        if verbose:
            print(f"Dry run enabled, skipped writing updated JSON for '{json_path}'.")
        return

    with open(json_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=4, ensure_ascii=False)
    if verbose:
        print(f"Updated JSON with tables saved to '{json_path}'.")


def write_tables_json(output_path, tables):
    with open(output_path, "w", encoding="utf-8") as file:
        json_data = {"table": tables}
        import json
        json.dump(json_data, file, indent=4, ensure_ascii=False)


def write_tables_csv(output_path, table_rows):
    fieldnames = ["table_name", "table_source", "criterion", "group", "spell_name", "spell_source"]
    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in table_rows:
            writer.writerow(row)


def write_tables_xlsx(output_path, table_rows):
    criteria_order = ["Name", "Background", "Class", "Subclass"]
    df = pd.DataFrame(table_rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if df.empty:
            df.to_excel(writer, sheet_name="Tables", index=False)
            return

        all_sheet_df = df.sort_values(by=["criterion", "group", "spell_name"], key=lambda col: col.astype(str).str.casefold())
        all_sheet_df.to_excel(writer, sheet_name="All Tables", index=False)

        for criterion in criteria_order:
            criterion_df = df[df["criterion"] == criterion]
            if criterion_df.empty:
                continue
            criterion_df = criterion_df.sort_values(by=["group", "spell_name"], key=lambda col: col.astype(str).str.casefold())
            criterion_df.to_excel(writer, sheet_name=criterion, index=False)


def preload_classes(file_path, sheet_name, classes_list):
    """
    Preload both main classes and subclasses from the Excel file into dictionaries using the provided classes_list.

    Parameters:
    - file_path (str): Path to the Excel file.
    - sheet_name (str): Excel sheet name.
    - classes_list (list): The predefined list of classes and their sources.

    Returns:
    - tuple: A tuple of two dictionaries:
        - main_classes_by_background: {background_name: [{"name": class_name, "source": class_source}]}
        - subclass_info: {
            background_name: [
                {
                    "class_name": parent_class_name,
                    "class_source": parent_class_source,
                    "subclass": {"name": subclass_name, "shortName": short_name, "source": subclass_source}
                }
            ]
        }
    """
    try:

        # Load the Excel sheet
        data = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

        # Normalize column names to avoid mismatches
        data.columns = data.columns.str.strip().str.lower()

        # Initialize the dictionaries
        background_classes = {}
        background_subclasses = {}

        # Create a mapping for main classes and subclasses
        main_classes_map = {class_data["name"].lower(): class_data["source"] for class_data in classes_list}
        subclasses_map = {}
        for class_data in classes_list:
            for subclass in class_data.get("sub_classes", []):
                subclasses_map[subclass["name"].lower()] = {
                    "class_name": class_data["name"],
                    "class_source": class_data["source"],
                    "shortName": subclass["shortName"],
                    "source": subclass["source"]
                }

        # Process each row (background)
        for _, row in data.iterrows():
            background_name = row.iloc[0].strip()  # First column contains the background name
            classes = []
            subclasses = []

            # Check each column (after the first one)
            for col_idx in range(1, len(row)):
                if str(row.iloc[col_idx]).strip().upper() == 'X':  # If 'X' is found
                    # Get the class name from the header
                    class_or_subclass_name = data.columns[col_idx].strip()

                    # Check if it is a main class
                    if class_or_subclass_name.lower() in main_classes_map:
                        classes.append({
                            "name": class_or_subclass_name.capitalize(),
                            "source": main_classes_map[class_or_subclass_name.lower()]
                        })

                    # Check if it is a subclass
                    elif class_or_subclass_name.lower() in subclasses_map:
                        subclass_info = subclasses_map[class_or_subclass_name.lower()]
                        subclasses.append({
                            "class_name": subclass_info["class_name"],
                            "class_source": subclass_info["class_source"],
                            "subclass": {
                                "name": class_or_subclass_name.capitalize(),
                                "shortName": subclass_info["shortName"],
                                "source": subclass_info["source"]
                            }
                        })

            # Save classes and subclasses for the background if any are found
            if classes:
                background_classes[background_name] = classes
            if subclasses:
                background_subclasses[background_name] = subclasses

        return background_classes, background_subclasses

    except Exception as e:
        raise ValueError(f"Error loading classes and subclasses from Excel: {e}")




def update_spells_with_classes(json_path, file_path, sheet_name, valid_backgrounds, locations, classes_list,
                               output_json_path=None, verbose=True, dry_run=False):
    """
    Updates the spell JSON by adding both "classes" and "subclasses" fields
    inside the "classes" object based on valid backgrounds and preloaded class/subclass data.

    Parameters:
    - json_path (str): Path to the JSON file containing spells.
    - file_path (str): Path to the Excel file.
    - sheet_name (str): Excel sheet name.
    - valid_backgrounds (list): List of valid backgrounds.
    - locations (list): Valid locations for filtering spells.
    - classes_list (list): The predefined list of classes and sources (main classes and subclasses).
    - output_json_path (str): Path to save the updated JSON. Defaults to None.
    - verbose (bool): Enable verbose output. Defaults to True.
    - dry_run (bool): If True, do not write updated spell JSON to disk.

    Returns:
    - dict: The updated JSON content.
    """
    import json

    try:
        # Preload classes and subclasses for each background
        background_classes, background_subclasses = preload_classes(file_path, sheet_name, classes_list)

        # Load the spell JSON
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Ensure the "spell" key exists
        if "spell" not in data:
            raise ValueError("Invalid JSON structure: Missing 'spell' key.")

        # Convert lists to sets for faster lookup
        valid_background_set = set(valid_backgrounds)
        location_set = set(locations)

        # Iterate through spells
        for spell in data["spell"]:
            spell_name = spell.get("name", "Unknown Spell")

            try:
                # Get backgrounds associated with the spell
                backgrounds = spell.get("backgrounds", [])
                if not backgrounds:
                    if verbose:
                        print(f"Skipping spell '{spell_name}' - No backgrounds found.")
                    continue

                # Filter valid backgrounds for the spell
                valid_backgrounds_for_spell = [
                    background["name"] if isinstance(background, dict) else background
                    for background in backgrounds
                    if (background["name"] if isinstance(background, dict) else background) in valid_background_set
                ]

                if not valid_backgrounds_for_spell:
                    if verbose:
                        print(f"Skipping spell '{spell_name}' - No valid backgrounds.")
                    continue

                # Collect main classes and subclasses for all valid backgrounds
                final_classes = []
                final_subclasses = []
                seen_classes = set()  # Track classes added to avoid adding subclasses

                for background_name in valid_backgrounds_for_spell:
                    # Add main classes
                    if background_name in background_classes:
                        for cls in background_classes[background_name]:
                            class_key = cls["name"].lower()
                            if class_key not in seen_classes:
                                final_classes.append(cls)
                                seen_classes.add(class_key)

                    # Add subclasses (only if the parent class is not already included)
                    if background_name in background_subclasses:
                        for subclass_info in background_subclasses[background_name]:
                            class_key = subclass_info["class_name"].lower()
                            if class_key not in seen_classes:
                                final_subclasses.append({
                                    "class": {
                                        "name": subclass_info["class_name"],
                                        "source": subclass_info["class_source"]
                                    },
                                    "subclass": subclass_info["subclass"]
                                })

                # Wrap everything inside the "classes" field
                spell["classes"] = {
                    "fromClassList": final_classes,
                    "fromSubclass": final_subclasses
                }

                if verbose:
                    print(
                        f"Updated spell '{spell_name}' with classes: {final_classes} and subclasses: {final_subclasses}")

            except Exception as e:
                if verbose:
                    print(f"Error processing spell '{spell_name}': {e}")
                continue

        # Save the updated JSON
        if output_json_path and not dry_run:
            with open(output_json_path, 'w', encoding='utf-8') as output_file:
                json.dump(data, output_file, indent=4, ensure_ascii=False)
                if verbose:
                    print(f"Updated JSON saved to '{output_json_path}'.")
        elif output_json_path and dry_run:
            if verbose:
                print(f"Dry run enabled, skipped writing updated JSON for '{json_path}'.")
        else:
            print(json.dumps(data, indent=4, ensure_ascii=False))

        return data

    except Exception as e:
        raise Exception(f"An error occurred while processing '{json_path}': {e}")







if __name__ == "__main__":
    args = parse_args()

    # File paths
    json_paths = args.json_paths if args.json_paths else DEFAULT_JSON_PATHS
    file_path = "C:/Users/emmae/OneDrive/Shared/D&D/Tools/Guild Wars D&D.xlsx"
    sheet_name = "Spell Distribution"


    # Define your lists as provided
    classes_list = [
        {
            "name": "Apothecary", "source": "guidedrakkenheim", "sub_classes": [
            {"name": "Alienist", "shortName": "Alienist", "source": "guidedrakkenheim"},
            {"name": "Chemist", "shortName": "Chemist", "source": "guidedrakkenheim"},
            {"name": "Exorcist", "shortName": "Exorcist", "source": "guidedrakkenheim"},
            {"name": "Mutagenist", "shortName": "Mutagenist", "source": "guidedrakkenheim"},
            {"name": "Pathogenist", "shortName": "Pathogenist", "source": "guidedrakkenheim"},
            {"name": "Reanimator", "shortName": "Reanimator", "source": "guidedrakkenheim"}
        ]},
        {"name": "Artificer", "source": "efa", "sub_classes": [
            {"name": "Alchemist", "shortName": "Alchemist", "source": "efa"},
            {"name": "Armorer", "shortName": "Armorer", "source": "efa"},
            {"name": "Artillerist", "shortName": "Artillerist", "source": "efa"},
            {"name": "Battle Smith", "shortName": "Battle Smith", "source": "efa"},
            {"name": "Cartographer", "shortName": "Cartographer", "source": "efa"},
            {"name": "Forge Adept", "shortName": "Forge Adept", "source": "exploringeberron24"},
            {"name": "Maverick", "shortName": "Maverick", "source": "exploringeberron24"} 
        ]},
        {
            "name": "Barbarian", "source": "XPHB", "sub_classes": [
            {"name": "Ragetotem Spiritualist", "shortName": "Ragetotem Spiritualist", "source": "ragetotemspiritualist"}
        ]},
        {"name": "Bard", "source": "XPHB", "sub_classes": [
            {"name": "Collage of Dance", "shortName": "Dance", "source": "XPHB"},
            {"name": "Collage of Glamour", "shortName": "Glamour", "source": "XPHB"},
            {"name": "Collage of Lore", "shortName": "Lore", "source": "XPHB"},
            {"name": "Collage of Swords", "shortName": "Swords", "source": "XGE"},
            {"name": "Collage of the Moon", "shortName": "Moon", "source": "FRHoF"},
            {"name": "Collage of Valor", "shortName": "Valor", "source": "XPHB"},
            {"name": "Collage of Whispers", "shortName": "Whispers", "source": "XGE"},
            {"name": "Virtuoso", "shortName": "Virtuoso", "source": "GW2EoD"}
        ]},
        {"name": "Cleric", "source": "XPHB", "sub_classes": [
            {"name": "Death Domain", "shortName": "Death", "source": "DMG"},
            {"name": "Forge Domain", "shortName": "Forge", "source": "XGE"},
            {"name": "Grave Domain", "shortName": "Grave", "source": "XGE"},
            {"name": "Inquisition Domain", "shortName": "Inquisition", "source": "GrimHollowPlayerPack"},
            {"name": "Knowledge Domain", "shortName": "Knowledge", "source": "FRHoF"},
            {"name": "Life Domain", "shortName": "Life", "source": "XPHB"},
            {"name": "Light Domain", "shortName": "Light", "source": "XPHB"},
            {"name": "Nature Domain", "shortName": "Nature", "source": "PHB"},
            {"name": "Tempest Domain", "shortName": "Tempest", "source": "PHB"},
            {"name": "Trickery Domain", "shortName": "Trickery", "source": "XPHB"},
            {"name": "War Domain", "shortName": "War", "source": "XPHB"}
        ]},
        {"name": "Druid", "source": "XPHB", "sub_classes": [
            {"name": "Circle of Dreams", "shortName": "Dreams", "source": "XGE"},
            {"name": "Circle of Land", "shortName": "Land", "source": "XPHB"},
            {"name": "Circle of Moon", "shortName": "Moon", "source": "XPHB"},
            {"name": "Circle of Sea", "shortName": "Sea", "source": "XPHB"},
            {"name": "Circle of Spores", "shortName": "Spores", "source": "TCE"},
            {"name": "Circle of Stars", "shortName": "Stars", "source": "XPHB"},
            {"name": "Circle of the Shepherd", "shortName": "Shepherd", "source": "XGE"}
        ]},
        {"name": "Fighter", "source": "XPHB", "sub_classes": [
            {"name": "Eldritch Knight", "shortName": "Eldritch Knight", "source": "XPHB"}
        ]},
        {"name": "Gunslinger", "source": "ValdaGunslinger", "sub_classes": [
            {"name": "Spellslinger", "shortName": "Spellslinger", "source": "ValdaGunslinger"}
        ]},
        {"name": "Illrigger", "source": "IllriggerRevised", "sub_classes": [
            {"name": "Architect of Ruin", "shortName": "Architect of Ruin", "source": "IllriggerRevised"}
        ]},
        {"name": "Paladin", "source": "XPHB", "sub_classes": [
            {"name": "Oath of Conquest", "shortName": "Conquest", "source": "XGE"},
            {"name": "Oath of Devotion", "shortName": "Devotion", "source": "XPHB"},
            {"name": "Oath of Glory", "shortName": "Glory", "source": "XPHB"},
            {"name": "Oath of Redemption", "shortName": "Redemption", "source": "XGE"},
            {"name": "Oath of Vengeance", "shortName": "Vengeance", "source": "XPHB"},
            {"name": "Oath of the Ancients", "shortName": "Ancients", "source": "XPHB"},
            {"name": "Oath of the Noble Genies", "shortName": "Noble Genies", "source": "FRHoF"},
            {"name": "Oathbreaker", "shortName": "Oathbreaker", "source": "DMG"}
        ]},
        {"name": "Psion", "source": "xua2025psion", "sub_classes": [
            {"name": "Metamorph", "shortName": "Metamorph", "source": "xua2025psion"},
            {"name": "Psi Warper", "shortName": "Psi Warper", "source": "xua2025psion"},
            {"name": "Psykinetic", "shortName": "Psykinetic", "source": "xua2025psion"},
            {"name": "Telepath", "shortName": "Telepath", "source": "xua2025psion"}
        ]},
        {"name": "Ranger", "source": "XPHB", "sub_classes": [
            {"name": "Beast Master", "shortName": "Beast Master", "source": "XPHB"},
            {"name": "Fey Wanderer", "shortName": "Fey Wanderer", "source": "XPHB"},
            {"name": "Gloom Stalker", "shortName": "Gloom Stalker", "source": "XPHB"},
            {"name": "Hollow Warden", "shortName": "Hollow Warden", "source": "xua2025horrorsubclasses"},
            {"name": "Horizon Walker", "shortName": "Horizon Walker", "source": "XGE"},
            {"name": "Hunter", "shortName": "Hunter", "source": "XPHB"},
            {"name": "Monster Slayer", "shortName": "Monster Slayer", "source": "XGE"},
            {"name": "Winter Walker", "shortName": "Winter Walker", "source": "FRHoF"}
        ]},
        {"name": "Rogue", "source": "XPHB", "sub_classes": [
            {"name": "Arcane Trickster", "shortName": "Arcane Trickster", "source": "XPHB"}
        ]},
        {"name": "Sorcerer", "source": "XPHB", "sub_classes": [
            {"name": "Aberrant Sorcery", "shortName": "Aberrant", "source": "XPHB"},
            {"name": "Clockwork Sorcery", "shortName": "Clockwork", "source": "XPHB"},
            {"name": "Divine Soul", "shortName": "Divine Soul", "source": "XGE"},
            {"name": "Draconic Sorcery", "shortName": "Draconic", "source": "XPHB"},
            {"name": "Shadow Magic", "shortName": "Shadow Magic", "source": "XGE"},
            {"name": "Spellfire Sorcery", "shortName": "Spellfire", "source": "FRHoF"},
            {"name": "Storm Sorcery", "shortName": "Storm", "source": "XGE"},
            {"name": "Wild Magic", "shortName": "Wild Magic", "source": "XPHB"}
        ]},
        {"name": "Warlock", "source": "XPHB", "sub_classes": [
            {"name": "Archfey Patron", "shortName": "Archfey", "source": "XPHB"},
            {"name": "Celestial Patron", "shortName": "Celestial", "source": "XPHB"},
            {"name": "Fiend Patron", "shortName": "Fiend", "source": "XPHB"},
            {"name": "Great Old One Patron", "shortName": "Great Old One", "source": "XPHB"},
            {"name": "The Fathomless", "shortName": "Fathomless", "source": "TCE"},
            {"name": "The Hexblade", "shortName": "Hexblade", "source": "XGE"},
            {"name": "Cosmic Patron", "shortName": "Cosmic", "source": "guidedrakkenheim"},
        ]},
        {"name": "Witch", "source": "WorldsBeyondNumberWitch", "sub_classes": [
            {"name": "Coven of the Claw", "shortName": "Claw", "source": "WorldsBeyondNumberWitch"}
        ]},
        {"name": "Wizard", "source": "XPHB", "sub_classes": [
            {"name": "Abjurer", "shortName": "Abjurer", "source": "XPHB"},
            {"name": "Bladesinger", "shortName": "Bladesinger", "source": "FRHoF"},
            {"name": "Diviner", "shortName": "Diviner", "source": "XPHB"},
            {"name": "Evoker", "shortName": "Evoker", "source": "XPHB"},
            {"name": "Illusionist", "shortName": "Illusionist", "source": "XPHB"},
            {"name": "Occultist", "shortName": "Occultist", "source": "crookedmoon24"},
            {"name": "School of Conjuration", "shortName": "Conjuration", "source": "PHB"},
            {"name": "School of Enchantment", "shortName": "Enchantment", "source": "PHB"},
            {"name": "School of Necromancy", "shortName": "Necromancy", "source": "PHB"},
            {"name": "School of Transmutation", "shortName": "Transmutation", "source": "PHB"},
            {"name": "Wizard of the Citadel", "shortName": "Citadel", "source": "WizardCitadelWBN"},
            {"name": "War", "shortName": "War", "source": "XGE"}
        ]}
    ]
    valid_backgrounds = [
        "No Attribute", "Strength", "Axe Mastery", "Hammer Mastery", "Swordsmanship", "Tactics",
        "No Attribute - Warrior", "Expertise", "Beast Mastery", "Marksmanship", "Wilderness Survival",
        "No Attribute - Ranger", "Divine Favor", "Healing Prayers", "Smiting Prayers", "Protection Prayers",
        "No Attribute - Monk", "Soul Reaping", "Curses", "Blood Magic", "Death Magic", "No Attribute - Necromancer",
        "Fast Casting", "Domination Magic", "Illusion Magic", "Inspiration Magic", "No Attribute - Mesmer",
        "Energy Storage", "Air Magic", "Earth Magic", "Fire Magic", "Water Magic", "No Attribute - Elementalist",
        "Critical Strikes", "Dagger Mastery", "Deadly Arts", "Shadow Arts", "No Attribute - Assassin",
        "Spawning Power", "Channeling Magic", "Communing", "Restoration Magic", "No Attribute - Ritualist",
        "Leadership", "Command", "Motivation", "Spear Mastery", "No Attribute - Paragon",
        "Mysticism", "Earth Prayers", "Scythe Mastery", "Wind Prayers", "No Attribute - Dervish"
    ]
    locations_list = []

    # Call the function to update spells
    for json_path in json_paths:
        try:
            updated_data = update_spells_with_classes(
                json_path=json_path,
                file_path=file_path,
                sheet_name=sheet_name,
                valid_backgrounds=valid_backgrounds,
                locations=locations_list,
                classes_list=classes_list,
                output_json_path=json_path,
                verbose=args.verbose,
                dry_run=args.dry_run,
            )
        except Exception as error:
            print(f"Skipping '{json_path}': {error}")
            continue

        if not args.generate_tables:
            continue

        spells = updated_data.get("spell", [])
        tables = generate_spell_tables(spells, args.table_criteria)
        table_rows = flatten_tables_for_tabular_export(tables)

        remove_generated_tables(updated_data)
        add_generated_tables(updated_data, tables)
        save_json_with_tables(json_path, updated_data, dry_run=args.dry_run, verbose=args.verbose)

        source_file_name = os.path.splitext(os.path.basename(json_path))[0]
        safe_base_name = sanitize_filename(source_file_name)
        output_dir = os.path.abspath(args.tables_output_dir)
        os.makedirs(output_dir, exist_ok=True)
        remove_old_table_exports(output_dir, safe_base_name, verbose=args.verbose)

        if "json" in args.table_formats:
            json_output_path = os.path.join(output_dir, f"{safe_base_name} - Spell Tables.json")
            write_tables_json(json_output_path, tables)
            if args.verbose:
                print(f"Wrote table JSON: {json_output_path}")

        if "csv" in args.table_formats:
            csv_output_path = os.path.join(output_dir, f"{safe_base_name} - Spell Tables.csv")
            write_tables_csv(csv_output_path, table_rows)
            if args.verbose:
                print(f"Wrote table CSV: {csv_output_path}")

        if "xlsx" in args.table_formats:
            xlsx_output_path = os.path.join(output_dir, f"{safe_base_name} - Spell Tables.xlsx")
            write_tables_xlsx(xlsx_output_path, table_rows)
            if args.verbose:
                print(f"Wrote table XLSX: {xlsx_output_path}")

