# HandOff - Blend Mode Compatibility

Reference for blend-mode compatibility across common artwork formats. It includes modes HandOff does not write; use the main Layer blend modes chapter for this build’s actual writer support.

OCA adopts **Krita** blend-mode semantics as its reference. Similar names in Photoshop do not always mean identical mathematics, colour spaces, or alpha treatment.

## Common blend modes

| OCA mode | Krita mode | Photoshop |
| --- | --- | --- |
| `normal` | `normal` | `Normal` |
| `multiply` | `multiply` | `Multiply` |
| `screen` | `screen` | `Screen` |
| `add` | `add` | `Linear Dodge (Add)` |
| `linear_dodge` | `linear_dodge` | `Linear Dodge (Add)` |
| `overlay` | `overlay` | `Overlay` |
| `darken` | `darken` | `Darken` |
| `lighten` | `lighten` | `Lighten` |
| `burn` | `burn` | `Color Burn` |
| `dodge` | `dodge` | `Color Dodge` |
| `soft_light` | `soft_light_svg` | `Soft Light` |
| `hard_light` | `hard_light` | `Hard Light` |
| `difference` | `diff` | `Difference` |
| `exclusion` | `exclusion` | `Exclusion` |
| `color` | `color` | `Color` |
| `luminosity` | `luminize` | `Luminosity` |
| `hue` | `hue` | `Hue` |
| `saturation` | `saturation` | `Saturation` |
| `divide` | `divide` | `Divide` |
| `erase` | `erase` | - |

## Extended OCA/Krita modes

<details>
<summary>Expand the 91 less-common mode mappings</summary>

| OCA mode | Krita mode | Photoshop |
| --- | --- | --- |
| `inverse_subtract` | `inverse_subtract` | - |
| `subtract` | `subtract` | `Subtract` |
| `darker_color` | `darker color` | `Darker Color` |
| `easy_burn` | `easy burn` | - |
| `fog_darken` | `fog_darken_ifs_illusions` | - |
| `gamma_dark` | `gamma_dark` | - |
| `linear_burn` | `linear_burn` | `Linear Burn` |
| `shade` | `shade_ifs_illusions` | - |
| `converse` | `converse` | - |
| `and` | `and` | - |
| `implication` | `implication` | - |
| `nand` | `nand` | - |
| `nor` | `nor` | - |
| `not_converse` | `not_converse` | - |
| `not_implication` | `not_implication` | - |
| `or` | `or` | - |
| `xnor` | `xnor` | - |
| `xor` | `xor` | - |
| `dissolve` | `dissolve` | `Dissolve` |
| `increase_luminosity` | `inc_luminosity` | - |
| `increase_saturation` | `inc_saturation` | - |
| `decrease_luminosity` | `dec_luminosity` | - |
| `decrease_saturation` | `dec_saturation` | - |
| `divisive_modulo` | `divisive_modulo` | - |
| `allanon` | `allanon` | - |
| `alpha_darken` | `alphadarken` | - |
| `stencil_alpha` | `destination-in` | - |
| `hard_overlay` | `hard overlay` | - |
| `interpolation` | `interpolation` | - |
| `double_interpolation` | `interpolation 2x` | - |
| `hard_mix` | `hard mix` | - |
| `hard_mix_photoshop` | `hard_mix_photoshop` | `Hard Mix` |
| `parallel` | `parallel` | - |
| `penumbra_a` | `penumbra a` | - |
| `penumbra_b` | `penumbra a` | - |
| `penumbra_c` | `penumbra a` | - |
| `penumbra_d` | `penumbra a` | - |
| `greater` | `greater` | - |
| `geometric_mean` | `geometric_mean` | - |
| `additive_subtractive` | `additive_subtractive` | - |
| `negation` | `negation` | - |
| `arc_tangent` | `arc_tangent` | - |
| `equivalence` | `equivalence` | - |
| `freeze_reflect` | `freeze_reflect` | - |
| `freeze` | `freeze` | - |
| `glow_heat` | `glow_heat` | - |
| `heat` | `heat` | - |
| `heat_glow` | `heat_glow` | - |
| `heat_glow_freeze_reflect` | `heat_glow_freeze_reflect_hybrid` | - |
| `glow` | `glow` | - |
| `reflect_freeze` | `reflect_freeze` | - |
| `reflect` | `reflect` | - |
| `increase_intensity` | `inc_intensity` | - |
| `increase_saturation_hsi` | `inc_saturation_hsi` | - |
| `color_hsi` | `color_hsi` | - |
| `decrease_intensity` | `dec_intensity` | - |
| `decrease_saturation_hsi` | `dec_saturation_hsi` | - |
| `intensity` | `intensity` | - |
| `saturation_hsi` | `saturation_hsi` | - |
| `hue_hsi` | `hue_hsi` | - |
| `increase_lightness` | `inc_lightness` | - |
| `increase_saturation_hsl` | `inc_saturation_hsl` | - |
| `color_hsl` | `color_hsl` | - |
| `decrease_lightness` | `dec_lightness` | - |
| `decrease_saturation_hsl` | `dec_saturation_hsl` | - |
| `lightness` | `lightness` | - |
| `saturation_hsl` | `saturation_hsl` | - |
| `hue_hsl` | `hue_hsl` | - |
| `increase_saturation_hsv` | `inc_saturation_hsv` | - |
| `increase_value` | `inc_value` | - |
| `color_hsv` | `color_hsv` | - |
| `decrease_saturation_hsv` | `dec_saturation_hsv` | - |
| `decrease_value` | `dec_value` | - |
| `saturation_hsv` | `saturation_hsv` | - |
| `value` | `value` | - |
| `lighter_color` | `lighter color` | `Lighter Color` |
| `easy_dodge` | `easy dodge` | - |
| `flat_light` | `flat_light` | - |
| `fog_lighten` | `fog_lighten_ifs_illusions` | - |
| `linear_light` | `linear light` | `Linear Light` |
| `gamma_illumination` | `gamma_illumination` | - |
| `luminosity_sai` | `luminosity_sai` | - |
| `gamma_light` | `gamma_light` | - |
| `pin_light` | `pin_light` | `Pin Light` |
| `vivid_light` | `vivid_light` | `Vivid Light` |
| `pnorm_a` | `pnorm_a` | - |
| `pnorm_b` | `pnorm_b` | - |
| `soft_light_ifs` | `soft_light_ifs_illusions` | - |
| `soft_light_pegtop_delphi` | `soft_light_pegtop_delphi` | - |
| `super_light` | `super_light` | - |
| `tint` | `tint_ifs_illusions` | - |

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
