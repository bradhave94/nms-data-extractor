# Unused MXML/MBIN Data We Could Use

Summary of fields present in the game tables that we currently **don’t** extract but could be useful for apps, wikis, or tooling.

---

## Products (`nms_reality_gcproducttable.MXML`)

| Field | Type | Use |
|-------|------|-----|
| **Level** | int | Item level (0 = no level). |
| **Rarity** | enum | Common, Uncommon, Rare, etc. |
| **Legality** | enum | Legal / Illegal (smuggled goods). |
| **Consumable** | bool | Can be consumed (e.g. food). |
| **ChargeValue** | int | Charge amount if used for charging tech. |
| **Category** (SubstanceCategory) | enum | Catalyst, Fuel, etc. (game category). |
| **Type** (ProductCategory) | enum | Component, etc. (game type). |
| **TradeCategory** | enum | None / Legal / Illegal – good for filtering trade goods. |
| **WikiCategory** | string | e.g. "Crafting" – for wiki/filters. |
| **CookingIngredient** | bool | Usable in cooking (we infer usages but don’t store this raw). |
| **CookingValue** | float | Cooking stat value (we have it in cooking JSON only). |
| **FoodBonusStat** / **FoodBonusStatAmount** | enum + float | Which stat food boosts and by how much. |
| **GoodForSelling** | bool | Marked good for selling. |
| **EggModifierIngredient** | bool | Usable in egg sequencer. |
| **CanSendToOtherPlayers** | bool | Trade/gift flag. |
| **DefaultCraftAmount** / **CraftAmountStepSize** / **CraftAmountMultiplier** | int/float | Crafting UI defaults. |
| **Cost** | GcItemPriceModifiers | SpaceStationMarkup, LowPriceMod, HighPriceMod, BuyBaseMarkup – economy. |
| **NormalisedValueOnWorld** / **NormalisedValueOffWorld** | float | Economy weighting on/off planet. |
| **HeroIcon** | path | Alternative/large icon (often empty). |
| **NameLower** | loc key | Short/lowercase name key. |
| **Hint** / **PinObjective** / **PinObjectiveTip** | loc keys | UI hints and pin text. |

---

## Substances / Raw materials (`nms_reality_gcsubstancetable.MXML`)

| Field | Type | Use |
|-------|------|-----|
| **Symbol** | loc key | Short symbol (e.g. for refinery/UI). |
| **WorldColour** | RGBA | In-world colour (we only use UI Colour). |
| **Category** (SubstanceCategory) | enum | Fuel, Catalyst, Earth, etc. |
| **Rarity** | enum | Common, Uncommon, Rare. |
| **Legality** | enum | Legal / Illegal. |
| **ChargeValue** | int | Used when charging tech. |
| **TradeCategory** | enum | Trade classification. |
| **WikiEnabled** | bool | Whether it appears in wiki. |
| **CookingIngredient** | bool | Usable in cooking. |
| **GoodForSelling** | bool | Sell hint. |
| **EasyToRefine** | bool | Refinery hint. |
| **EggModifierIngredient** | bool | Egg sequencer. |
| **PinObjective** / **PinObjectiveTip** / **PinObjectiveMessage** | loc keys | UI/pin text. |
| **PinObjectiveScannableType** | enum | e.g. Carbon – scanner icon type. |
| **WikiMissionID** | string | Wiki/mission link. |

---

## Technology (`nms_reality_gctechnologytable.MXML`)

| Field | Type | Use |
|-------|------|-----|
| **Level** | int | Tech level. |
| **Chargeable** | bool | We derive HasChargedBy; raw value useful. |
| **ChargeAmount** | int | Max charge. |
| **ChargeType** (SubstanceCategory) | enum | e.g. Catalyst, Earth. |
| **ChargeBy** | list of product IDs | Which items can charge this tech (e.g. CATALYST1, POWERCELL). |
| **Upgrade** | bool | Is upgrade module (vs core). |
| **Core** | bool | Is core tech. |
| **RepairTech** | bool | Used for repairs. |
| **Category** (TechnologyCategory) | enum | Suit, Ship, Weapon, etc. |
| **Rarity** (TechnologyRarity) | enum | Common, Rare, etc. |
| **BaseStat** | enum | e.g. Suit_Protection – main stat. |
| **RequiredRank** | int | Narrative/rank requirement. |
| **DispensingRace** | enum | Which race sells it (Explorers, etc.). |
| **FragmentCost** | int | Salvaged Data cost. |
| **TechShopRarity** | enum | Shop availability (e.g. Impossible). |
| **ParentTechId** | string | Parent tech for tree/layout. |
| **RequiredTech** | string | Tech prerequisite. |
| **RequiredLevel** | int | Level prerequisite. |
| **DamagedDescription** | loc key | Text when broken. |
| **WikiEnabled** | bool | Wiki visibility. |

---

## Buildings (`basebuildingobjectstable.MXML`)

| Field | Type | Use |
|-------|------|-----|
| **IconOverrideProductID** | product ID | If set, icon comes from this product (we could resolve to PNG path). |
| **PlacementScene** | path | Model path for placement preview. |
| **BuildableOnPlanetBase** / **BuildableOnSpaceBase** / **BuildableOnFreighter** | bool | Where it can be built. |
| **BuildableInShipStructural** / **BuildableInShipDecorative** | bool | Ship building. |
| **BuildableOnPlanet** / **BuildableUnderwater** / **BuildableAboveWater** | bool | Environment. |
| **PlanetLimit** / **RegionLimit** / **PlanetBaseLimit** / **FreighterBaseLimit** | int | Build limits. |
| **Groups** | list | Group + SubGroupName (e.g. PLANET_TECH, PLANETPORTABLE) – we only use one group. |
| **CanChangeColour** / **CanChangeMaterial** | bool | Customisation. |
| **CanPickUp** | bool | Portable. |
| **ShowInBuildMenu** | bool | Shown in build menu. |
| **LinkGridData** | object | Power/network connection (Connection.Network, Rate, Storage). |
| **IsDecoration** / **IsPlaceable** | bool | Type of part. |
| **Biome** | enum | All / Lush / etc. |
| **StorageContainerIndex** | int | If ≥ 0, storage container slot. |
| **ColourPaletteGroupId** / **DefaultColourPaletteId** | string | Theming. |
| **MaterialGroupId** / **DefaultMaterialId** | string | Material set. |
| **EditsTerrain** | bool | Terrain edit part. |

---

## Consumables / Cooking (`consumableitemtable.MXML`)

We get name/icon from the **product** table; consumable table has:

| Field | Type | Use |
|-------|------|-----|
| **RewardID** | string | Reward table entry when consumed (e.g. R_FOOD_UNIT). |
| **ButtonLocID** / **ButtonSubLocID** | loc keys | Button label when using. |
| **DestroyItemWhenConsumed** | bool | One-shot vs reusable. |
| **CloseInventoryWhenUsed** | bool | UX. |
| **RequiresCanAffordCost** / **RequiresMissionActive** | string | Gating. |
| **RewardOverrideTable** | ref | Override rewards. |

---

## Refinery (`nms_reality_gcrecipetable.MXML`)

We already extract: recipe ID, inputs, output, time, operation. Possible extras:

- **RecipeType** / **RecipeName** (if present) for better labels.
- Any **Category** or **Tag** fields for filtering (if the table has them).

---

## Quick wins (high value, low effort)

1. **Products:** **Rarity**, **Legality**, **TradeCategory**, **WikiCategory**, **Consumable**, **CookingIngredient**, **GoodForSelling**, **EggModifierIngredient** – all simple booleans/enums.
2. **Raw materials:** **Category** (SubstanceCategory), **Rarity**, **CookingIngredient**, **Symbol** (translate for short name).
3. **Technology:** **Category** (TechnologyCategory), **Rarity**, **Chargeable**, **ChargeBy** (list of charge product IDs), **Upgrade**, **Core**, **ParentTechId**, **RequiredTech**.
4. **Buildings:** **IconOverrideProductID** (resolve to product icon for `data/images`), **BuildableOnPlanetBase** / **BuildableOnSpaceBase** / **BuildableOnFreighter**, **Groups** (full list + SubGroupName), **LinkGridData** (power/network) for base builders.

If you tell me which of these you want in the JSON first (e.g. “Products: Rarity + TradeCategory” or “Technology: Category + ChargeBy”), I can outline the exact parser changes next.
