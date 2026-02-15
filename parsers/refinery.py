"""Parse Refinery recipes from MXML to JSON"""
from .base_parser import EXMLParser
from pathlib import Path


# Cache for item names lookup
_item_names_cache = None


def _load_item_names():
    """Load item names from Products and Substances tables"""
    global _item_names_cache
    if _item_names_cache is not None:
        return _item_names_cache

    _item_names_cache = {}
    parser = EXMLParser()
    parser.load_localization()

    def get_translated_name(item_id, name_key):
        """Try multiple translation patterns to find the English name"""
        if not name_key:
            return item_id

        # Try direct translation
        name = parser.translate(name_key, None)
        if name and name != name_key:
            return name

        # Try BUI_ prefix pattern
        bui_key = f"BUI_{item_id}"
        name = parser.translate(bui_key, None)
        if name:
            return name

        # Try TRA_ prefix pattern
        tra_key = f"TRA_{item_id}"
        name = parser.translate(tra_key, None)
        if name:
            return name

        # Try EXP_ prefix pattern
        exp_key = f"EXP_{item_id}"
        name = parser.translate(exp_key, None)
        if name:
            return name

        # Fall back to translating the key (makes it readable from KEY_NAME -> Key)
        return parser.translate(name_key, item_id)

    # Load from Products table
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    if products_path.exists():
        root = parser.load_xml(str(products_path))
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop:
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                name_key = parser.get_property_value(item, 'Name', '')
                if item_id:
                    _item_names_cache[item_id] = get_translated_name(item_id, name_key)

    # Load from Substances table
    substances_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcsubstancetable.MXML'
    if substances_path.exists():
        root = parser.load_xml(str(substances_path))
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop:
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                name_key = parser.get_property_value(item, 'Name', '')
                if item_id and name_key:
                    _item_names_cache[item_id] = get_translated_name(item_id, name_key)

    print(f"[OK] Loaded {len(_item_names_cache)} item names for lookup")
    return _item_names_cache


def _get_item_name(item_id: str) -> str:
    """Get the English name for an item ID"""
    names = _load_item_names()
    return names.get(item_id, item_id)


def parse_refinery(mxml_path: str, only_refinery: bool = True) -> list:
    """
    Parse nms_reality_gcrecipetable.MXML to Refinery.json format.

    Target JSON structure:
    {
        "Id": "ref1",
        "Inputs": [{"Id": "conTech90", "Quantity": 1}],
        "Output": {"Id": "raw56", "Quantity": 15},
        "Time": "1.28",
        "Operation": "Requested Operation: Nanite Extraction"
    }

    Args:
        mxml_path: Path to the MXML file
        only_refinery: If True, only include non-cooking recipes (Cooking=false)

    Returns:
        List of recipe dictionaries
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    parser.load_localization()

    recipes = []
    recipe_counter = 1

    # Navigate to Table property containing all recipes
    # Structure: <Data><Property name="Table"><Property name="Table" (array of recipes)>
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return recipes

    # Each recipe is a Property element with value="GcRefinerRecipe"
    for recipe_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Get recipe ID
            recipe_id = parser.get_property_value(recipe_elem, 'Id', f'RECIPE_{recipe_counter}')

            # Get operation name (RecipeName or RecipeType)
            recipe_name_key = parser.get_property_value(recipe_elem, 'RecipeName', '')
            recipe_type = parser.get_property_value(recipe_elem, 'RecipeType', '')
            operation_key = recipe_name_key if recipe_name_key else recipe_type

            # Translate operation name
            operation = parser.translate(operation_key, operation_key)
            # If still a key, try to make it more readable
            if operation == operation_key and operation.startswith('R_'):
                operation = f"Refinery: {operation[2:]}"  # Strip R_ prefix
            elif operation == operation_key and operation.startswith('RECIPE_'):
                operation = f"Recipe: {operation[7:]}"  # Strip RECIPE_ prefix

            # Check if this is a cooking recipe
            is_cooking = parser.get_property_value(recipe_elem, 'Cooking', 'false')
            is_cooking_bool = parser.parse_value(is_cooking)

            # Skip based on filter
            if only_refinery and is_cooking_bool:
                continue  # Skip cooking recipes for refinery output
            if not only_refinery and not is_cooking_bool:
                continue  # Skip refinery recipes for cooking output

            # Get time to make
            time_str = parser.get_property_value(recipe_elem, 'TimeToMake', '0')

            # Parse Ingredients (Inputs)
            inputs = []
            ingredients_prop = recipe_elem.find('.//Property[@name="Ingredients"]')
            if ingredients_prop is not None:
                for ingredient in ingredients_prop.findall('./Property'):
                    ing_id = parser.get_property_value(ingredient, 'Id', '')
                    ing_amount = parser.get_property_value(ingredient, 'Amount', '1')
                    if ing_id:
                        inputs.append({
                            'Id': ing_id,
                            'Name': _get_item_name(ing_id),
                            'Quantity': parser.parse_value(ing_amount)
                        })

            # Parse Result (Output)
            output = {}
            result_prop = recipe_elem.find('.//Property[@name="Result"]')
            if result_prop is not None:
                output_id = parser.get_property_value(result_prop, 'Id', '')
                output_amount = parser.get_property_value(result_prop, 'Amount', '1')
                output = {
                    'Id': output_id,
                    'Name': _get_item_name(output_id),
                    'Quantity': parser.parse_value(output_amount)
                }

            # Create recipe entry
            recipe = {
                'Id': recipe_id,  # Use actual game ID
                'Inputs': inputs,
                'Output': output,
                'Time': str(round(float(time_str), 2)),  # Round to 2 decimals
                'Operation': operation
            }

            recipes.append(recipe)
            recipe_counter += 1

        except Exception as e:
            print(f"Warning: Skipped recipe due to error: {e}")
            continue

    recipe_type = "refinery" if only_refinery else "cooking"
    print(f"[OK] Parsed {len(recipes)} {recipe_type} recipes")
    return recipes


def parse_nutrient_processor(mxml_path: str) -> list:
    """
    Parse cooking recipes from nms_reality_gcrecipetable.MXML to NutrientProcessor.json format.

    This uses the same structure as Refinery.json but filters for Cooking=true recipes.

    Args:
        mxml_path: Path to the MXML file

    Returns:
        List of cooking recipe dictionaries
    """
    return parse_refinery(mxml_path, only_refinery=False)
