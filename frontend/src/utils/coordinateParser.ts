/**
 * Utility functions for parsing and converting coordinate formats
 * Supports multiple formats:
 * - Decimal degrees: 48.123456 or -17.654321
 * - Degrees and decimal minutes: N48°52.01' or S12°30.5'
 * - Degrees, minutes, and seconds: N48°52'00.6" or E18°0'15"
 * - European DMS with comma separator: 49° 13' 57,63" N or 18° 36' 33,396" E
 * - Compact aviation format: 491400N or 0183649E
 */

export interface CoordinateParseResult {
  value: number | null;
  isValid: boolean;
  error?: string;
}

/**
 * Parse latitude from various formats to decimal degrees
 * Valid range: -90 to 90
 */
export function parseLatitude(input: string): CoordinateParseResult {
  const trimmed = input.trim();

  if (!trimmed) {
    return { value: null, isValid: false, error: 'Input is empty' };
  }

  // Try parsing as decimal number first
  const decimal = parseDecimalCoordinate(trimmed);
  if (decimal !== null) {
    if (decimal < -90 || decimal > 90) {
      return { value: null, isValid: false, error: 'Latitude must be between -90 and 90' };
    }
    return { value: decimal, isValid: true };
  }

  // Try parsing DMS/DM format
  const dms = parseDMSCoordinate(trimmed, 'latitude');
  if (dms !== null) {
    if (dms < -90 || dms > 90) {
      return { value: null, isValid: false, error: 'Latitude must be between -90 and 90' };
    }
    return { value: dms, isValid: true };
  }

  return { value: null, isValid: false, error: 'Invalid latitude format' };
}

/**
 * Parse longitude from various formats to decimal degrees
 * Valid range: -180 to 180
 */
export function parseLongitude(input: string): CoordinateParseResult {
  const trimmed = input.trim();

  if (!trimmed) {
    return { value: null, isValid: false, error: 'Input is empty' };
  }

  // Try parsing as decimal number first
  const decimal = parseDecimalCoordinate(trimmed);
  if (decimal !== null) {
    if (decimal < -180 || decimal > 180) {
      return { value: null, isValid: false, error: 'Longitude must be between -180 and 180' };
    }
    return { value: decimal, isValid: true };
  }

  // Try parsing DMS/DM format
  const dms = parseDMSCoordinate(trimmed, 'longitude');
  if (dms !== null) {
    if (dms < -180 || dms > 180) {
      return { value: null, isValid: false, error: 'Longitude must be between -180 and 180' };
    }
    return { value: dms, isValid: true };
  }

  return { value: null, isValid: false, error: 'Invalid longitude format' };
}

/**
 * Parse decimal coordinate format
 * Examples: 48.123456, -17.654321, +12.5
 */
function parseDecimalCoordinate(input: string): number | null {
  // Remove spaces
  const cleaned = input.replace(/\s/g, '');

  // Check if it's a valid number
  const num = parseFloat(cleaned);
  if (isNaN(num)) {
    return null;
  }

  // Ensure it looks like a decimal coordinate (no special characters except +/- and .)
  if (!/^[+-]?\d+(\.\d+)?$/.test(cleaned)) {
    return null;
  }

  return num;
}

/**
 * Parse DMS (Degrees Minutes Seconds) or DM (Degrees Minutes) format
 * Examples:
 * - N48°52'00.6"
 * - S12°30'15"
 * - N48°52.01'
 * - E18°0.25'
 * - W100°30'
 * - 49° 13' 57,63" N (European format with comma)
 * - 18° 36' 33,396" E (European format with comma)
 * - 491400N (aviation format: DDMMSS + direction)
 * - 0183649E (aviation format: DDDMMSS + direction)
 */
function parseDMSCoordinate(input: string, type: 'latitude' | 'longitude'): number | null {
  // Remove spaces and normalize comma to dot for decimal separator
  const cleaned = input.replace(/\s/g, '').replace(/,/g, '.');

  // Extract direction (N/S/E/W) if present
  let direction = '';
  let coordStr = cleaned;

  // Check for direction at start or end
  const directionMatch = cleaned.match(/^([NSEW])|([NSEW])$/i);
  if (directionMatch) {
    direction = (directionMatch[1] || directionMatch[2]).toUpperCase();
    coordStr = cleaned.replace(/^[NSEW]|[NSEW]$/i, '');
  }

  // Validate direction based on coordinate type
  if (direction) {
    if (type === 'latitude' && !['N', 'S'].includes(direction)) {
      return null;
    }
    if (type === 'longitude' && !['E', 'W'].includes(direction)) {
      return null;
    }
  }

  // Try to parse aviation compact format (e.g., 491400N or 0183649E)
  // Latitude: DDMMSS[N|S] (6 digits + direction)
  // Longitude: DDDMMSS[E|W] (7 digits + direction)
  if (direction && /^\d+$/.test(coordStr)) {
    const expectedLength = type === 'latitude' ? 6 : 7;
    if (coordStr.length === expectedLength) {
      const degreesLength = type === 'latitude' ? 2 : 3;
      const degrees = parseInt(coordStr.substring(0, degreesLength), 10);
      const minutes = parseInt(coordStr.substring(degreesLength, degreesLength + 2), 10);
      const seconds = parseInt(coordStr.substring(degreesLength + 2), 10);

      if (minutes >= 60 || seconds >= 60) {
        return null;
      }

      let decimal = degrees + minutes / 60 + seconds / 3600;

      // Apply direction
      if (direction === 'S' || direction === 'W') {
        decimal = -decimal;
      }

      return decimal;
    }
  }

  // Try to parse DMS format: 48°52'30.5" or 48°52'30"
  const dmsMatch = coordStr.match(/^(\d+(?:\.\d+)?)°(\d+(?:\.\d+)?)'(\d+(?:\.\d+)?)"?$/);
  if (dmsMatch) {
    const degrees = parseFloat(dmsMatch[1]);
    const minutes = parseFloat(dmsMatch[2]);
    const seconds = parseFloat(dmsMatch[3]);

    if (minutes >= 60 || seconds >= 60) {
      return null;
    }

    let decimal = degrees + minutes / 60 + seconds / 3600;

    // Apply direction
    if (direction === 'S' || direction === 'W') {
      decimal = -decimal;
    }

    return decimal;
  }

  // Try to parse DM format: 48°52.01' or 48°52'
  const dmMatch = coordStr.match(/^(\d+(?:\.\d+)?)°(\d+(?:\.\d+)?)'?$/);
  if (dmMatch) {
    const degrees = parseFloat(dmMatch[1]);
    const minutes = parseFloat(dmMatch[2]);

    if (minutes >= 60) {
      return null;
    }

    let decimal = degrees + minutes / 60;

    // Apply direction
    if (direction === 'S' || direction === 'W') {
      decimal = -decimal;
    }

    return decimal;
  }

  return null;
}

/**
 * Format a decimal coordinate to a string with specified precision
 */
export function formatDecimalCoordinate(value: number | null | undefined, precision: number = 6): string {
  if (value === null || value === undefined) {
    return '';
  }
  return value.toFixed(precision);
}

/**
 * Validate coordinate format without parsing
 * Returns true if the format is recognized
 */
export function isValidCoordinateFormat(input: string, type: 'latitude' | 'longitude'): boolean {
  if (!input || !input.trim()) {
    return false;
  }

  const result = type === 'latitude' ? parseLatitude(input) : parseLongitude(input);
  return result.isValid;
}

/**
 * Get example formats for help text
 */
export function getCoordinateExamples(type: 'latitude' | 'longitude'): string[] {
  if (type === 'latitude') {
    return [
      '48.123456 (decimal)',
      'N48°52.01\' (degrees, minutes)',
      'N48°52\'30" (DMS)',
      '49° 13\' 57,63" N (European DMS)',
      '491400N (compact aviation)',
    ];
  } else {
    return [
      '17.654321 (decimal)',
      'E18°0.25\' (degrees, minutes)',
      'E18°0\'15" (DMS)',
      '18° 36\' 33,396" E (European DMS)',
      '0183649E (compact aviation)',
    ];
  }
}
