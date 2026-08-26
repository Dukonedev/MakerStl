<?php
header("Access-Control-Allow-Origin: *");
header("Content-Type: application/json; charset=UTF-8");
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

/**
 * SVG Optimizer for Shared Hosting (No Dependencies)
 * Implements:
 * 1. Coordinate Rounding (2 decimals)
 * 2. Path Normalization (Relative -> Absolute)
 */
class SVGPathOptimizer {
    
    // Command lengths (number of parameters)
    private static $cmdLengths = [
        'M' => 2, 'm' => 2,
        'L' => 2, 'l' => 2,
        'H' => 1, 'h' => 1,
        'V' => 1, 'v' => 1,
        'C' => 6, 'c' => 6,
        'S' => 4, 's' => 4,
        'Q' => 4, 'q' => 4,
        'T' => 2, 't' => 2,
        'A' => 7, 'a' => 7,
        'Z' => 0, 'z' => 0
    ];

    public static function process($svgContent) {
        // Load SVG (using DOMDocument for robust parsing)
        $dom = new DOMDocument();
        // Disable error reporting for malformed HTML/SVG strictness
        libxml_use_internal_errors(true);
        $dom->loadXML($svgContent, LIBXML_NOENT | LIBXML_XINCLUDE | LIBXML_NOERROR | LIBXML_NOWARNING);
        libxml_clear_errors();

        $xpath = new DOMXPath($dom);
        // Register SVG namespace if present (often default)
        $rootNamespace = $dom->documentElement->lookupNamespaceUri(NULL); 
        if ($rootNamespace) {
            $xpath->registerNamespace('svg', $rootNamespace);
            $paths = $xpath->query('//svg:path');
        } else {
            $paths = $xpath->query('//path');
        }

        foreach ($paths as $path) {
            $d = $path->getAttribute('d');
            $newD = self::optimizePathData($d);
            $path->setAttribute('d', $newD);
        }

        return $dom->saveXML();
    }

    private static function optimizePathData($d) {
        $commands = self::parsePath($d);
        $newCommands = [];
        $x = 0; $y = 0; // Current cursor position
        $startX = 0; $startY = 0; // Start of current subpath (for Z)
        
        // Previous Control Point (for S and T commands)
        // If previous command was not C/S (for S) or Q/T (for T), control point is current point
        $prevCx = 0; $prevCy = 0;
        $prevCmd = '';

        foreach ($commands as $cmd) {
            $type = $cmd['type'];
            $args = $cmd['args'];
            $isRelative = ctype_lower($type);
            $ucType = strtoupper($type);

            // Output command variables
            $outType = $ucType; // Always convert to Absolute
            $outArgs = [];

            // Helper to update current pos
            $updatePos = function($nx, $ny) use (&$x, &$y) { $x = $nx; $y = $ny; };

            switch ($ucType) {
                case 'M': // Move
                    if ($isRelative) {
                        $x += $args[0]; $y += $args[1];
                    } else {
                        $x = $args[0]; $y = $args[1];
                    }
                    $startX = $x; $startY = $y;
                    $outArgs = [$x, $y];
                    
                    // Reset Control Point
                    $prevCx = $x; $prevCy = $y;
                    break;

                case 'L': // Line
                    if ($isRelative) {
                        $x += $args[0]; $y += $args[1];
                    } else {
                        $x = $args[0]; $y = $args[1];
                    }
                    $outArgs = [$x, $y];
                    $prevCx = $x; $prevCy = $y;
                    break;

                case 'H': // Horizontal Line
                    if ($isRelative) $x += $args[0];
                    else $x = $args[0];
                    
                    // Convert H to L for simplicity (L x y)
                    $outType = 'L';
                    $outArgs = [$x, $y];
                    $prevCx = $x; $prevCy = $y;
                    break;

                case 'V': // Vertical Line
                    if ($isRelative) $y += $args[0];
                    else $y = $args[0];
                    
                    // Convert V to L
                    $outType = 'L';
                    $outArgs = [$x, $y];
                    $prevCx = $x; $prevCy = $y;
                    break;

                case 'C': // Cubic Bezier (x1 y1 x2 y2 x y)
                    if ($isRelative) {
                        $cx1 = $x + $args[0]; $cy1 = $y + $args[1];
                        $cx2 = $x + $args[2]; $cy2 = $y + $args[3];
                        $x += $args[4]; $y += $args[5];
                    } else {
                        $cx1 = $args[0]; $cy1 = $args[1];
                        $cx2 = $args[2]; $cy2 = $args[3];
                        $x = $args[4]; $y = $args[5];
                    }
                    $outArgs = [$cx1, $cy1, $cx2, $cy2, $x, $y];
                    $prevCx = $cx2; $prevCy = $cy2; // Next S uses reflection of this
                    break;

                case 'S': // Smooth Cubic (x2 y2 x y)
                    // Calculate first control point (reflection of prevCx/Cy around x/y)
                    // If prev cmd was not C or S, control point is current point (x,y)
                    $isPrevCurve = ($prevCmd === 'C' || $prevCmd === 'S' || $prevCmd === 'c' || $prevCmd === 's');
                    
                    if ($isPrevCurve) {
                        $cx1 = 2 * $x - $prevCx;
                        $cy1 = 2 * $y - $prevCy;
                    } else {
                        $cx1 = $x;
                        $cy1 = $y;
                    }

                    if ($isRelative) {
                        $cx2 = $x + $args[0]; $cy2 = $y + $args[1];
                        $x += $args[2]; $y += $args[3];
                    } else {
                        $cx2 = $args[0]; $cy2 = $args[1];
                        $x = $args[2]; $y = $args[3];
                    }
                    
                    // Convert S to C explicitly for maximum compatibility
                    $outType = 'C';
                    $outArgs = [$cx1, $cy1, $cx2, $cy2, $x, $y];
                    $prevCx = $cx2; $prevCy = $cy2;
                    break;

                case 'Q': // Quadratic Bezier (x1 y1 x y)
                    if ($isRelative) {
                        $cx1 = $x + $args[0]; $cy1 = $y + $args[1];
                        $x += $args[2]; $y += $args[3];
                    } else {
                        $cx1 = $args[0]; $cy1 = $args[1];
                        $x = $args[2]; $y = $args[3];
                    }
                    $outArgs = [$cx1, $cy1, $x, $y];
                    $prevCx = $cx1; $prevCy = $cy1;
                    break;
                
                case 'T': // Smooth Quadratic (x y)
                    $isPrevCurve = ($prevCmd === 'Q' || $prevCmd === 'T' || $prevCmd === 'q' || $prevCmd === 't');
                    if ($isPrevCurve) {
                        $cx1 = 2 * $x - $prevCx;
                        $cy1 = 2 * $y - $prevCy;
                    } else {
                        $cx1 = $x;
                        $cy1 = $y;
                    }

                    if ($isRelative) {
                        $x += $args[0]; $y += $args[1];
                    } else {
                        $x = $args[0]; $y = $args[1];
                    }
                    
                    // Convert T to Q
                    $outType = 'Q';
                    $outArgs = [$cx1, $cy1, $x, $y];
                    $prevCx = $cx1; $prevCy = $cy1;
                    break;

                case 'A': // Arc (rx ry rot large sweep x y)
                    $rx = $args[0]; $ry = $args[1]; $rot = $args[2]; 
                    $large = $args[3]; $sweep = $args[4];
                    if ($isRelative) {
                        $x += $args[5]; $y += $args[6];
                    } else {
                        $x = $args[5]; $y = $args[6];
                    }
                    $outArgs = [$rx, $ry, $rot, $large, $sweep, $x, $y];
                    $prevCx = $x; $prevCy = $y;
                    break;

                case 'Z': // Close Path
                    $x = $startX; $y = $startY;
                    $outArgs = [];
                    $prevCx = $x; $prevCy = $y;
                    break;
            }

            // Update Previous Command Type (use the ORIGINAL from input to track logic correctly)
            $prevCmd = $type;

            // Round Args and format
            $strArgs = array_map(function($v) {
                return round((float)$v, 2);
            }, $outArgs);

            $newCommands[] = $outType . implode(' ', $strArgs);
        }

        return implode(' ', $newCommands);
    }

    private static function parsePath($d) {
        // Normalize space (commas to spaces)
        $d = str_replace(',', ' ', $d);
        // Split by commands (letter followed by numbers)
        // Regex: Look for [a-zA-Z]
        preg_match_all('/([a-zA-Z])([^a-zA-Z]*)/', $d, $matches, PREG_SET_ORDER);
        
        $commands = [];
        foreach ($matches as $m) {
            $type = $m[1];
            $argsStr = trim($m[2]);
            $args = [];
            if ($argsStr !== '') {
                $args = preg_split('/\s+/', $argsStr);
                $args = array_map('floatval', $args);
            }
            
            // Check if multiple command sets are condensed (e.g. L 10 10 20 20 -> L 10 10, L 20 20)
            $len = self::$cmdLengths[strtoupper($type)] ?? 0;
            if ($len > 0 && count($args) > $len) {
                // Split expanded commands (e.g. l 10 10 20 20 -> l 10 10, l 20 20)
                // However, subsequent implicit commands take the SAME type (l)
                // We handle the first one, then the rest as implicit
                $chunks = array_chunk($args, $len);
                foreach ($chunks as $chunk) {
                    if (count($chunk) === $len) {
                        $commands[] = ['type' => $type, 'args' => $chunk];
                    }
                }
            } else {
                $commands[] = ['type' => $type, 'args' => $args];
            }
        }
        return $commands;
    }
}

// Main Endpoint Logic
try {
    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        throw new Exception("File upload failed");
    }

    $tmpPath = $_FILES['file']['tmp_name'];
    $svgContent = file_get_contents($tmpPath);
    
    if (!$svgContent) throw new Exception("Empty file");

    $optimized = SVGPathOptimizer::process($svgContent);

    echo json_encode([
        'success' => true,
        'svg' => $optimized
    ]);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}
?>
