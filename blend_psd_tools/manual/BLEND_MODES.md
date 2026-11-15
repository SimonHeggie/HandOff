# Comp-IO - Blend Mode Compatibility

Reference for blend-mode compatibility across common artwork formats.

OCA adopts **Krita** blend-mode semantics as its reference. Similar names in Photoshop or After Effects do not always mean identical mathematics, colour spaces, or alpha treatment.

## Common blend modes

| OCA mode | Krita mode | Photoshop | After Effects |
|:--|:--|:--|:--|
| `normal` | `normal` | `Normal` | `NORMAL` |
| `multiply` | `multiply` | `Multiply` | `MULTIPLY` |
| `screen` | `screen` | `Screen` | `SCREEN` |
| `add` | `add` | `Linear Dodge (Add)` | `ADD` |
| `linear_dodge` | `linear_dodge` | `Linear Dodge (Add)` | `LINEAR_DODGE` |
| `overlay` | `overlay` | `Overlay` | `OVERLAY` |
| `darken` | `darken` | `Darken` | `DARKEN` |
| `lighten` | `lighten` | `Lighten` | `LIGHTEN` |
| `burn` | `burn` | `Color Burn` | `COLOR_BURN` |
| `dodge` | `dodge` | `Color Dodge` | `CLASSIC_COLOR_DODGE` |
| `soft_light` | `soft_light_svg` | `Soft Light` | `SOFT_LIGHT` |
| `hard_light` | `hard_light` | `Hard Light` | `HARD_LIGHT` |
| `difference` | `diff` | `Difference` | `DIFFERENCE` |
| `exclusion` | `exclusion` | `Exclusion` | `EXCLUSION` |
| `color` | `color` | `Color` | `COLOR` |
| `luminosity` | `luminize` | `Luminosity` | `LUMINOSITY` |
| `hue` | `hue` | `Hue` | `HUE` |
| `saturation` | `saturation` | `Saturation` | `SATURATION` |
| `divide` | `divide` | `Divide` | `DIVIDE` |
| `erase` | `erase` | - | `SILHOUETE_ALPHA` |

## Extended OCA/Krita modes

<details>
<summary>Expand the 91 less-common mode mappings</summary>

| OCA mode | Krita mode | Photoshop | After Effects |
|:--|:--|:--|:--|
| `inverse_subtract` | `inverse_subtract` | - | `LINEAR_BURN` |
| `subtract` | `subtract` | `Subtract` | `SUBTRACT` |
| `darker_color` | `darker color` | `Darker Color` | `DARKER_COLOR` |
| `easy_burn` | `easy burn` | - | `MULTIPLY (approx.)` |
| `fog_darken` | `fog_darken_ifs_illusions` | - | `DARKEN` |
| `gamma_dark` | `gamma_dark` | - | `VIVID_LIGHT (approx.)` |
| `linear_burn` | `linear_burn` | `Linear Burn` | `LINEAR_BURN` |
| `shade` | `shade_ifs_illusions` | - | `LINEAR_BURN (approx.)` |
| `converse` | `converse` | - | - |
| `and` | `and` | - | `LINEAR_BURN (approx.)` |
| `implication` | `implication` | - | - |
| `nand` | `nand` | - | - |
| `nor` | `nor` | - | - |
| `not_converse` | `not_converse` | - | - |
| `not_implication` | `not_implication` | - | - |
| `or` | `or` | - | `ADD (approx.)` |
| `xnor` | `xnor` | - | - |
| `xor` | `xor` | - | - |
| `dissolve` | `dissolve` | `Dissolve` | `DISSOLVE` |
| `increase_luminosity` | `inc_luminosity` | - | `ADD (approx.)` |
| `increase_saturation` | `inc_saturation` | - | `OVERLAY (approx.)` |
| `decrease_luminosity` | `dec_luminosity` | - | - |
| `decrease_saturation` | `dec_saturation` | - | - |
| `divisive_modulo` | `divisive_modulo` | - | - |
| `allanon` | `allanon` | - | - |
| `alpha_darken` | `alphadarken` | - | `LUMINESCENT_PREMUL` |
| `stencil_alpha` | `destination-in` | - | `STENCIL_ALPHA` |
| `hard_overlay` | `hard overlay` | - | `VIVID_LIGHT (approx.)` |
| `interpolation` | `interpolation` | - | - |
| `double_interpolation` | `interpolation 2x` | - | - |
| `hard_mix` | `hard mix` | - | `HARD_MIX (approx.)` |
| `hard_mix_photoshop` | `hard_mix_photoshop` | `Hard Mix` | `CLASSIC_COLOR_BURN (approx.)` |
| `parallel` | `parallel` | - | `DARKEN` |
| `penumbra_a` | `penumbra a` | - | - |
| `penumbra_b` | `penumbra a` | - | - |
| `penumbra_c` | `penumbra a` | - | - |
| `penumbra_d` | `penumbra a` | - | - |
| `greater` | `greater` | - | - |
| `geometric_mean` | `geometric_mean` | - | `MULTIPLY` |
| `additive_subtractive` | `additive_subtractive` | - | `DIFFERENCE (approx.)` |
| `negation` | `negation` | - | - |
| `arc_tangent` | `arc_tangent` | - | - |
| `equivalence` | `equivalence` | - | `DIFFERENCE` |
| `freeze_reflect` | `freeze_reflect` | - | `OVERLAY` |
| `freeze` | `freeze` | - | - |
| `glow_heat` | `glow_heat` | - | - |
| `heat` | `heat` | - | - |
| `heat_glow` | `heat_glow` | - | `HARD_LIGHT (approx.)` |
| `heat_glow_freeze_reflect` | `heat_glow_freeze_reflect_hybrid` | - | - |
| `glow` | `glow` | - | - |
| `reflect_freeze` | `reflect_freeze` | - | - |
| `reflect` | `reflect` | - | - |
| `increase_intensity` | `inc_intensity` | - | - |
| `increase_saturation_hsi` | `inc_saturation_hsi` | - | - |
| `color_hsi` | `color_hsi` | - | `COLOR (approx.)` |
| `decrease_intensity` | `dec_intensity` | - | - |
| `decrease_saturation_hsi` | `dec_saturation_hsi` | - | - |
| `intensity` | `intensity` | - | `LUMINOSITY (approx.)` |
| `saturation_hsi` | `saturation_hsi` | - | `SATURATION (approx.)` |
| `hue_hsi` | `hue_hsi` | - | `HUE (approx.)` |
| `increase_lightness` | `inc_lightness` | - | - |
| `increase_saturation_hsl` | `inc_saturation_hsl` | - | - |
| `color_hsl` | `color_hsl` | - | - |
| `decrease_lightness` | `dec_lightness` | - | - |
| `decrease_saturation_hsl` | `dec_saturation_hsl` | - | - |
| `lightness` | `lightness` | - | - |
| `saturation_hsl` | `saturation_hsl` | - | - |
| `hue_hsl` | `hue_hsl` | - | - |
| `increase_saturation_hsv` | `inc_saturation_hsv` | - | - |
| `increase_value` | `inc_value` | - | - |
| `color_hsv` | `color_hsv` | - | - |
| `decrease_saturation_hsv` | `dec_saturation_hsv` | - | - |
| `decrease_value` | `dec_value` | - | - |
| `saturation_hsv` | `saturation_hsv` | - | - |
| `value` | `value` | - | - |
| `lighter_color` | `lighter color` | `Lighter Color` | `LIGHTER_COLOR` |
| `easy_dodge` | `easy dodge` | - | - |
| `flat_light` | `flat_light` | - | `VIVID_LIGHT (approx.)` |
| `fog_lighten` | `fog_lighten_ifs_illusions` | - | `LIGHTEN (approx.)` |
| `linear_light` | `linear light` | `Linear Light` | `LINEAR_LIGHT` |
| `gamma_illumination` | `gamma_illumination` | - | - |
| `luminosity_sai` | `luminosity_sai` | - | `ADD` |
| `gamma_light` | `gamma_light` | - | - |
| `pin_light` | `pin_light` | `Pin Light` | `PIN_LIGHT` |
| `vivid_light` | `vivid_light` | `Vivid Light` | `COLOR_BURN (approx.)` |
| `pnorm_a` | `pnorm_a` | - | - |
| `pnorm_b` | `pnorm_b` | - | - |
| `soft_light_ifs` | `soft_light_ifs_illusions` | - | `SOFT_LIGHT` |
| `soft_light_pegtop_delphi` | `soft_light_pegtop_delphi` | - | `SOFT_LIGHT (approx.)` |
| `super_light` | `super_light` | - | `PIN_LIGHT (approx.)` |
| `tint` | `tint_ifs_illusions` | - | - |

</details>

### Interpretation and cautions

- **Blank cells** indicate no vetted name mapping in the registry. They do not prove the target application lacks an equivalent.
- An **approximation** is never safe to substitute silently. Confirm with a composite comparison.
- Additive artwork in Spine uses the Photoshop **Linear Dodge (Add)** mode; OCA `add` is modelled on Krita.
- Promote a blend mode from multiple child layers to a group only after checking compositing equivalence.
- The supplied OCA reference repeated `penumbra a` for three other penumbra variants; these should not drive unattended translations.

## Credits and source documentation

- **[Nicolas Dufresne (Duduf) / RxLaboratorio](https://oca.rxlab.guide/specs/blending-modes.html)** - Open Cel Animation - Blending Modes.
- **[Krita contributors / KDE](https://docs.krita.org/en/reference_manual/blending_modes.html)** - Krita 5.3 reference manual - Blending Modes.
- **[Adobe](https://helpx.adobe.com/sg/photoshop/desktop/repair-retouch/adjust-light-tone/blending-mode-descriptions.html)** - Photoshop - Blending mode descriptions.
- **[Esoteric Software](https://us.esotericsoftware.com/spine-import-psd)** - Spine User Guide - Import PSD.

**Nicolas Dufresne (Duduf), RxLaboratorio**: OCA blend-mode correspondence material; **Krita/KDE contributors**: blend-mode definitions; **Adobe**: Photoshop mode documentation; **Esoteric Software**: supported Spine PSD blend modes.
