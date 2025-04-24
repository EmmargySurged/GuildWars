import pandas as pd
import json


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
        import pandas as pd

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
                               output_json_path=None, verbose=True):
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

    Returns:
    - None: Saves the updated JSON or prints the output.
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
        if output_json_path:
            with open(output_json_path, 'w', encoding='utf-8') as output_file:
                json.dump(data, output_file, indent=4, ensure_ascii=False)
                if verbose:
                    print(f"Updated JSON saved to '{output_json_path}'.")
        else:
            print(json.dumps(data, indent=4, ensure_ascii=False))

    except Exception as e:
        raise Exception(f"An error occurred: {e}")







# Example Usage
if __name__ == "__main__":
    # File paths
    json_path = "./Guild_Wars_Shared.json"
    file_path = "C:/Users/emmae/OneDrive/Shared/D&D/Tools/Guild Wars Spell Conversion - Spreadsheet.xlsx"
    sheet_name = "Spell Distribution"
    output_path = "./Updated_Guild_Wars_Spells.json"

    # Define your lists as provided
    classes_list = [
        {"name": "Artificer", "source": "TCE", "sub_classes": [
            {"name": "Alchemist", "shortName": "Alchemist", "source": "TCE"},
            {"name": "Armorer", "shortName": "Armorer", "source": "TCE"},
            {"name": "Artillerist", "shortName": "Artillerist", "source": "TCE"},
            {"name": "Battle Smith", "shortName": "Battle Smith", "source": "TCE"}
        ]},
        {"name": "Bard", "source": "XPHB", "sub_classes": [
            {"name": "Collage of Lore", "shortName": "Lore", "source": "XPHB"},
            {"name": "Collage of Swords", "shortName": "Swords", "source": "XGE"}
        ]},
        {"name": "Cleric", "source": "XPHB", "sub_classes": [
            {"name": "Inquisition Domain", "shortName": "Inquisition", "source": "GH:PP"},
            {"name": "Light Domain", "shortName": "Light", "source": "XPHB"}
        ]},
        {"name": "Druid", "source": "XPHB", "sub_classes": [
            {"name": "Circle of Spores", "shortName": "Spores", "source": "TCE"},
            {"name": "Circle of Stars", "shortName": "Stars", "source": "XPHB"}
        ]},
        {"name": "Illrigger", "source": "IllR", "sub_classes": [
            {"name": "Architect of Ruin", "shortName": "Architect of Ruin", "source": "IllR"}
        ]},
        {"name": "Paladin", "source": "XPHB", "sub_classes": [
            {"name": "Oath of Ancients", "shortName": "Ancients", "source": "XPHB"}
        ]},
        {"name": "Ranger", "source": "XPHB", "sub_classes": [
            {"name": "Beast Master", "shortName": "Beast Master", "source": "XPHB"}
        ]},
        {"name": "Sorcerer", "source": "XPHB", "sub_classes": [
            {"name": "Divine Soul", "shortName": "Divine Soul", "source": "XGE"}
        ]},
        {"name": "Warlock", "source": "XPHB", "sub_classes": [
            {"name": "The Fathomless", "shortName": "Fathomless", "source": "TCE"},
            {"name": "The Hexblade", "shortName": "Hexblade", "source": "XGE"}
        ]},
        {"name": "Witch", "source": "WBNW", "sub_classes": [
            {"name": "Coven of the Claw", "shortName": "Claw", "source": "WBNW"}
        ]},
        {"name": "Wizard", "source": "XPHB", "sub_classes": [
            {"name": "Bladesinging", "shortName": "Bladesinging", "source": "TCE"},
            {"name": "School of Necromancy", "shortName": "Necromancy", "source": "PHB"}
        ]},
        {"name": "Rogue", "source": "XPHB", "sub_classes": [
            {"name": "Arcane Trickster", "shortName": "Arcane Trickster", "source": "XPHB"}
        ]}
        ,
        {"name": "Fighter", "source": "XPHB", "sub_classes": [
            {"name": "Eldritch Knight", "shortName": "Eldritch Knight", "source": "XPHB"}
        ]}
    ]
    # Unused, maybe make custom classes the players can then also check.
    proficiencies_list = ['Light Armor', 'Medium Armor', 'Heavy Armor', 'Simple Weapons', 'Martial Weapons']
    valid_backgrounds = [
        "Strength", "Axe Mastery", "Hammer Mastery", "Swordsmanship", "Tactics",
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
    # Unused, just explain to players to select the correct backgrounds
    locations_list = ['Pre-Searing', 'Ascalon', 'Northern Shiverpeaks', 'Northeastern Kryta']

    # Call the function to update spells
    update_spells_with_classes(
        json_path=json_path,
        file_path=file_path,
        sheet_name=sheet_name,
        valid_backgrounds=valid_backgrounds,
        locations=locations_list,
        classes_list=classes_list,
        output_json_path=output_path,
        verbose=True
    )

