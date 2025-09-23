# PAPI (Precision Approach Path Indicator) Technical Documentation

## Overview
The Precision Approach Path Indicator (PAPI) is a visual aid that provides guidance information to help pilots acquire and maintain the correct approach angle during landing. This system uses light units positioned beside the runway that display different combinations of red and white lights based on the aircraft's approach angle.

## System Components

### Standard Configuration
- **4-light system (Standard PAPI)**: Four light units arranged in a horizontal bar
- **2-light system (A-PAPI)**: Abbreviated system with two light units for smaller airports

### Physical Layout
- **Location**: Left side of runway, approximately 300 meters from landing threshold
- **Distance from runway edge**: 15 meters (minimum 14 meters)
- **Spacing between units**: 9 meters
- **Orientation**: Perpendicular to runway centerline

## Operating Principle

### Light Beam Characteristics
Each PAPI unit emits a split beam:
- **Upper segment**: White light
- **Lower segment**: Red light
- **Transition zone**: Maximum 3 minutes of arc between colors

### Angular Settings (3-degree approach)
The four units are set at different angles:
1. **Unit 1 (furthest from runway)**: 2°30' (2.50°)
2. **Unit 2**: 2°50' (2.83°)
3. **Unit 3**: 3°10' (3.17°)
4. **Unit 4 (nearest to runway)**: 3°30' (3.50°)

The designated glideslope is 3°00', midway between units 2 and 3.

## Color Indications and Meanings

| White Lights | Red Lights | Approach Angle | Status |
|-------------|------------|----------------|--------|
| 4 | 0 | >3.5° | Too high |
| 3 | 1 | ~3.2° | Slightly high |
| 2 | 2 | 3.0° | On glidepath |
| 1 | 3 | ~2.8° | Slightly low |
| 0 | 4 | <2.5° | Too low |

### Pilot Memory Aid
"White on red, you're ahead (high)"
"Red on white, you're alright (on path)"
"All white, you're high as a kite"
"All red, you're dead (too low)"

## Technical Specifications

### Light Sources
- **Traditional**: 200W halogen lamps (2-3 per unit)
- **Modern LED**: ~50W per unit, 40,000+ hour lifespan
- **Intensity**: High-intensity beams visible up to:
  - Day: 5 miles (8 km) for guidance
  - Night: 20+ miles (32 km) for visibility

### Power and Control
- **Style A**: Power Control Unit (PCU) with photocell for automatic day/night adjustment
- **Style B**: L-828 constant current regulator
- **Remote control**: L-854 radio controller compatibility

### Environmental Requirements
- **Frangibility**: Units must break away safely on impact
- **Jet blast resistance**: Must withstand turbulence from aircraft
- **Weather resistance**: Operates in all weather conditions

## Detection Challenges for Computer Vision

### Key Characteristics for Detection
1. **Spatial arrangement**: 4 lights in horizontal line with consistent spacing
2. **Color profile**: Distinct red/white color signatures
3. **Intensity**: High brightness relative to background
4. **Position**: Located beside runway, predictable location
5. **Size**: Small but bright point sources in images

### Environmental Factors
- **Atmospheric conditions**: Fog, rain affect visibility
- **Ambient lighting**: Dawn/dusk conditions change contrast
- **Viewing angle**: Different perspectives from various approach angles
- **Distance**: Light size and intensity vary with range

## Quality Assessment Parameters

### RGB Analysis Requirements
1. **Red light characteristics**:
   - High R value (typically >200)
   - Low G and B values (<100)
   - R/G ratio > 2.0

2. **White light characteristics**:
   - Balanced RGB values
   - All channels typically >200
   - R≈G≈B (within 10-20% variance)

3. **Consistency checks**:
   - Similar intensity across units of same color
   - Color temperature consistency
   - Brightness uniformity (±15% tolerance)

### Critical Measurements
- **Inter-light spacing**: Should be consistent
- **Alignment**: Horizontal alignment verification
- **Color purity**: Measure color saturation
- **Intensity balance**: Compare brightness levels
- **Transition sharpness**: Red-white boundary clarity

## Regulatory Standards
- **ICAO Annex 14**: International standards for aerodrome design
- **FAA AC 150/5345-28**: US specifications for PAPI systems
- **Transport Canada TP312**: Canadian aerodrome standards

## Maintenance Requirements
- Regular calibration of angles (quarterly)
- Lamp replacement monitoring
- Color filter inspection
- Alignment verification
- Intensity measurement

## Image Processing Considerations

### Detection Strategy
1. **Pre-processing**: Noise reduction, contrast enhancement
2. **Light detection**: Bright spot detection using thresholding
3. **Grouping**: Identify 4-light clusters with proper spacing
4. **Color classification**: Analyze RGB values for red/white determination
5. **Validation**: Verify geometric arrangement and consistency

### Quality Metrics
- Position accuracy (pixel-level precision)
- Color classification confidence
- Intensity measurements
- Geometric consistency
- Temporal stability (for video)