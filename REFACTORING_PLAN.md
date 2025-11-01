# Video Processing Refactoring Plan

## Current State
- **File**: `backend/app/services/video_processor.py`
- **Size**: 5,146 lines
- **Classes**: 13 classes in a single file
- **Problem**: Transition visualization bars never appear in videos because:
  1. Videos generated BEFORE transition angles computed
  2. Need two-pass architecture: measurements first, then video generation

## Critical Path (Phase 1 - THIS SESSION)
**Goal**: Get transition bars working in videos

### Step 1: Fix Integer Conversion Bug ✅
- Fixed `roi_width` and `roi_height` to use `int()`
- Location: `video_processor.py:2820-2821`

### Step 2: Create Two-Pass Architecture
**Pass 1 - Collect Measurements**:
- Read video frame-by-frame
- Track lights, measure RGB, intensity, angles
- Return measurements list (NO video generation)

**Compute Transition Angles**:
- Use measurements from Pass 1
- Compute chromacity-based transition angles using existing `compute_transition_angles_from_chromacity()`
- Inject into measurements

**Pass 2 - Generate Videos**:
- Read video again frame-by-frame
- Use complete measurements (WITH transition angles)
- Generate enhanced video with bars visible
- Generate 4 individual PAPI videos with bars visible

### Step 3: Modify process_video_full() in papi_measurements.py
Current flow:
```python
measurements, videos, enhanced = process_video_single_pass()  # Videos FIRST
transition_angles = compute_transitions(measurements)  # Angles AFTER
# Result: Videos don't have transition data!
```

New flow:
```python
# PASS 1: Measurements only
measurements = collect_measurements_only(video)
transition_angles = compute_transitions(measurements)
inject_transitions_into_measurements(measurements, transition_angles)

# PASS 2: Generate videos with complete data
videos, enhanced = generate_videos_with_measurements(video, measurements)
# Result: Videos HAVE transition data!
```

## Full Refactoring (Phase 2 - FUTURE)
**Goal**: Split monolithic file into maintainable modules

### Proposed Structure
```
backend/app/services/video_processing/
├── __init__.py                  # Public API exports
├── models.py                    # Data classes (GPSData, DetectedLight, TrackedPAPILight)
├── gps.py                       # GPSExtractor class
├── detection.py                 # RunwayLightDetector, PreciseLightDetector
├── tracking.py                  # PAPILightTracker
├── measurement_collector.py     # Pass 1: Measurement collection
├── video_generator.py           # Pass 2: Video generation with overlays
├── reports.py                   # PAPIReportGenerator
├── utils.py                     # GPUAccelerator, caching, batch processing
└── transition_angles.py         # compute_transition_angles_from_chromacity
```

### Class Distribution
- **models.py**: `GPSData`, `DetectedLight`, `TrackedPAPILight` (~100 lines)
- **gps.py**: `GPSExtractor` (~400 lines)
- **detection.py**: `RunwayLightDetector`, `PreciseLightDetector` (~900 lines)
- **tracking.py**: `PAPILightTracker` (~600 lines)
- **measurement_collector.py**: NEW - measurement-only pass (~300 lines)
- **video_generator.py**: `PAPIVideoGenerator` refactored (~1500 lines)
- **reports.py**: `PAPIReportGenerator` (~400 lines)
- **utils.py**: `GPUAccelerator`, `FrameProcessingCache`, `BatchFrameProcessor` (~400 lines)
- **transition_angles.py**: `compute_transition_angles_from_chromacity` method extraction (~200 lines)

### Migration Steps (Phase 2)
1. Create all module files with appropriate imports
2. Move classes preserving functionality
3. Update `__init__.py` to export public API
4. Update all imports in:
   - `video_processor.py` (keep as facade)
   - `papi_measurements.py`
   - Any other files importing from video_processor
5. Run full test suite
6. Remove old video_processor.py once migration complete

## Testing Checklist
- [ ] Transition bars appear in enhanced video (main video)
- [ ] Transition bars appear in all 4 PAPI individual videos
- [ ] Bars show correct colors (red/gray/white sections)
- [ ] Green position indicator moves correctly
- [ ] Transition angle values displayed correctly
- [ ] PAPI light size is ~33% of individual video width
- [ ] All existing functionality still works
- [ ] No performance regression

## Implementation Status
- [x] Analysis complete
- [x] Bug fix (integer conversion)
- [x] Refactoring plan documented
- [ ] Two-pass architecture implemented
- [ ] Transition bars working
- [ ] Full module split (Phase 2 - deferred)

## Notes
- Original `process_video_single_pass()` mixed concerns (measurement + generation)
- True separation requires reading video twice (acceptable for correctness)
- Performance: ~2x slower than buggy single-pass, but 100% correct results
- Future optimization: Cache decoded frames in memory during Pass 1 for Pass 2 reuse
