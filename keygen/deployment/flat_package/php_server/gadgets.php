<?php
// Gadgets Manager - SVGs + Metadata

error_reporting(0);
ini_set('display_errors', 0);

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS, DELETE");
header("Access-Control-Allow-Headers: Content-Type, Content-Length, Accept-Encoding");
header("Content-Type: application/json");

if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    http_response_code(200);
    exit;
}

ob_start();

function send_response($data) {
    ob_clean();
    echo json_encode($data);
    exit;
}

$toolsDir = __DIR__ . '/../gadgets/';
if (!file_exists($toolsDir)) {
    if (!@mkdir($toolsDir, 0755, true)) {
        // Continue, check writable later
    }
}

$dataFile = $toolsDir . 'gadgets.json';

try {
    $rawInput = file_get_contents('php://input');
    $jsonData = json_decode($rawInput, true) ?? [];

    $action = $_POST['action'] ?? $_GET['action'] ?? $jsonData['action'] ?? '';

    // Load existing DB
    $gadgets = [];
    if (file_exists($dataFile)) {
        $content = file_get_contents($dataFile);
        $gadgets = json_decode($content, true) ?? [];
    }

    // --- ACTION: LIST ---
    if ($action === 'list') {
        send_response(['success' => true, 'gadgets' => $gadgets]);
    }

    // --- ACTION: SAVE (Create/Update) ---
    if ($action === 'save') {
        // Handle Metadata
        $id = $_POST['id'] ?? $jsonData['id'] ?? '';
        $name = $_POST['name'] ?? $jsonData['name'] ?? '';
        $description = $_POST['description'] ?? $jsonData['description'] ?? '';
        $widthMm = $_POST['widthMm'] ?? $jsonData['widthMm'] ?? 0;
        $heightMm = $_POST['heightMm'] ?? $jsonData['heightMm'] ?? 0;
        $baseExtrusionMm = $_POST['baseExtrusionMm'] ?? $jsonData['baseExtrusionMm'] ?? 2.0;
        $defaultColor = $_POST['defaultColor'] ?? $jsonData['defaultColor'] ?? '#ffffff';

        if (!$name) send_response(['success' => false, 'error' => 'Name is required']);

        // Generate ID if missing
        if (!$id) {
            $id = strtolower(preg_replace('/[^a-zA-Z0-9]/', '', $name)) . '_' . time();
        }

        // Ensure directory exists
        if (!is_dir($toolsDir)) {
            if (!@mkdir($toolsDir, 0755, true)) {
                send_response(['success' => false, 'error' => 'Cannot create gadgets directory. Permission denied.']);
            }
        }
        if (!is_writable($toolsDir)) {
             send_response(['success' => false, 'error' => 'Gadgets directory is not writable.']);
        }

        // Handle File Upload if present
        $svgUrl = $_POST['svgUrl'] ?? $jsonData['svgUrl'] ?? ''; // Keep existing if no file
        
        if (isset($_FILES['file']) && $_FILES['file']['error'] === UPLOAD_ERR_OK) {
            $file = $_FILES['file'];
            $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
            if ($ext !== 'svg') {
                send_response(['success' => false, 'error' => 'Only SVG files allowed']);
            }
            
            $filename = $id . '.svg';
            $targetPath = $toolsDir . $filename;
            
            if (@move_uploaded_file($file['tmp_name'], $targetPath)) {
                $svgUrl = 'gadgets/' . $filename; 
            } else {
                send_response(['success' => false, 'error' => 'Failed to move uploaded file. Check permissions.']);
            }
        }

        // Update or Add
        $newGadget = [
            'id' => $id,
            'name' => $name,
            'description' => $description,
            'widthMm' => floatval($widthMm),
            'heightMm' => floatval($heightMm),
            'baseExtrusionMm' => floatval($baseExtrusionMm),
            'defaultColor' => $defaultColor,
            'svgUrl' => $svgUrl
        ];

        // Replace if exists, else append
        $found = false;
        foreach ($gadgets as $k => $g) {
            if ($g['id'] === $id) {
                // Preserve svgUrl if not updated
                if (empty($svgUrl) && !empty($g['svgUrl'])) {
                    $newGadget['svgUrl'] = $g['svgUrl'];
                }
                $gadgets[$k] = $newGadget;
                $found = true;
                break;
            }
        }
        if (!$found) {
            $gadgets[] = $newGadget;
        }

        if (@file_put_contents($dataFile, json_encode($gadgets, JSON_PRETTY_PRINT)) === false) {
             send_response(['success' => false, 'error' => 'Failed to save metadata to gadgets.json']);
        }
        send_response(['success' => true, 'gadjet' => $newGadget]);
    }

    // --- ACTION: DELETE ---
    if ($action === 'delete') {
        $id = $_GET['id'] ?? $jsonData['id'] ?? '';
        if (!$id) send_response(['success' => false, 'error' => 'ID required']);

        $newGadgets = [];
        $deleted = false;
        foreach ($gadgets as $g) {
            if ($g['id'] === $id) {
                // Try delete file
                if (!empty($g['svgUrl'])) {
                    $fname = basename($g['svgUrl']);
                    $fpath = $toolsDir . $fname;
                    if (file_exists($fpath)) unlink($fpath);
                }
                $deleted = true;
                continue; // Skip adding to new array
            }
            $newGadgets[] = $g;
        }

        if ($deleted) {
            file_put_contents($dataFile, json_encode($newGadgets, JSON_PRETTY_PRINT));
            send_response(['success' => true]);
        } else {
            send_response(['success' => false, 'error' => 'Gadget not found']);
        }
    }

    send_response(['success' => false, 'error' => 'Invalid action']);

} catch (Throwable $t) {
    send_response(['success' => false, 'error' => $t->getMessage()]);
}
?>
