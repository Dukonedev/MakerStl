<?php
// Standalone Templates Handler - ULTRA ROBUST WITH OUTPUT BUFFERING
// capturing all stray output/errors to prevent Invalid JSON
ob_start(); 

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS, DELETE");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json");

if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    ob_end_clean(); // Clean anything before exiting
    http_response_code(200);
    exit;
}

// Disable native styling of errors just in case
ini_set('html_errors', 0); 
ini_set('display_errors', 0);
ini_set('log_errors', 1);
error_reporting(E_ALL);

function send_json_response($data) {
    // Clear any previous output (warnings, notices, HTML)
    if (ob_get_length()) ob_clean(); 
    echo json_encode($data);
    exit;
}

// Critical Error Handler
register_shutdown_function(function() {
    $error = error_get_last();
    if ($error && ($error['type'] === E_ERROR || $error['type'] === E_PARSE || $error['type'] === E_CORE_ERROR || $error['type'] === E_COMPILE_ERROR)) {
        if (ob_get_length()) ob_clean();
        header("Access-Control-Allow-Origin: *"); 
        header("Content-Type: application/json");
        echo json_encode(['success' => false, 'error' => "FATAL PHP ERROR: " . $error['message'] . " (Line " . $error['line'] . ")"]);
        exit;
    }
});

try {
    // Parse Input (JSON or POST)
    $rawInput = file_get_contents('php://input');
    $jsonData = json_decode($rawInput, true);

    // Determine Action
    $action = '';
    if (isset($_POST['action'])) {
        $action = $_POST['action'];
    } elseif (isset($_GET['action'])) {
        $action = $_GET['action'];
    } elseif ($jsonData && isset($jsonData['action'])) {
        $action = $jsonData['action'];
    }

    // Check POST Max Size Limit
    // Only throw if it looks like a failed upload (empty POST/FILES but content length > 0)
    // AND it's NOT a valid JSON request
    if ($_SERVER['REQUEST_METHOD'] == 'POST' && empty($_POST) && empty($_FILES) && $_SERVER['CONTENT_LENGTH'] > 0 && !$jsonData) {
        throw new Exception("File exceeds server limit (post_max_size).");
    }

    $templatesDir = __DIR__ . '/../templates/';

    // Attempt to creaate dir
    if (!file_exists($templatesDir)) {
        if (!@mkdir($templatesDir, 0755, true)) {
             // Continue, we will check writable later
        }
    }

    // --- ACTION: LIST ---
    if ($action === 'list') {
        if (!is_dir($templatesDir)) send_json_response(['success' => true, 'templates' => []]);
        
        $mode = $_GET['mode'] ?? 'public'; // 'public' or 'admin'
        
        $files = scandir($templatesDir);
        $templates = [];
        foreach ($files as $file) {
            if ($file === '.' || $file === '..') continue;
            
            $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
            if ($ext !== 'svg') continue;
            
            $isHidden = (strpos($file, '_hidden_') === 0);
            
            if ($mode === 'admin') {
                // Admin sees everything
                $templates[] = $file; 
            } else {
                // Public sees only visible files
                if (!$isHidden) {
                    $templates[] = $file;
                }
            }
        }
        send_json_response(['success' => true, 'templates' => $templates]);
    }

    // --- ACTION: RENAME ---
    if ($action === 'rename') {
        $input = json_decode(file_get_contents('php://input'), true);
        $oldName = $input['old_name'] ?? $_POST['old_name'] ?? '';
        $newName = $input['new_name'] ?? $_POST['new_name'] ?? '';
        
        if (!$oldName || !$newName) send_json_response(['success' => false, 'error' => 'Missing names']);
        
        // Security & Sanitization
        $oldName = basename($oldName);
        $cleanNewName = preg_replace('/[^a-zA-Z0-9 _-]/', '', $newName); // Keep safe chars
        if (empty($cleanNewName)) send_json_response(['success' => false, 'error' => 'Invalid new name']);
        
        // Preserve hidden status? No, user renames the base name. 
        // If file is hidden (_hidden_Name), and user renames to "New", should it stay hidden?
        // Let's assume user renames the *visible* part.
        // Actually, simplest is: User renames "File.svg" to "NewFile.svg".
        // If file is hidden, user probably wants to rename the file itself.
        // Let's just blindly rename oldPath to newPath constructed from sanitized input.
        // We will append .svg if missing.
        
        if (!str_ends_with(strtolower($cleanNewName), '.svg')) {
             $cleanNewName .= '.svg';
        }
        
        $oldPath = $templatesDir . $oldName;
        $newPath = $templatesDir . $cleanNewName;
        
        if (!file_exists($oldPath)) send_json_response(['success' => false, 'error' => 'File not found']);
        if (file_exists($newPath)) send_json_response(['success' => false, 'error' => 'Name already taken']);
        
        if (rename($oldPath, $newPath)) {
            send_json_response(['success' => true, 'new_name' => $cleanNewName]);
        } else {
            send_json_response(['success' => false, 'error' => 'Rename failed']);
        }
    }

    // --- ACTION: TOGGLE VISIBILITY ---
    if ($action === 'toggle_visibility') {
        $input = json_decode(file_get_contents('php://input'), true);
        $filename = $input['filename'] ?? $_POST['filename'] ?? '';
        
        if (!$filename) send_json_response(['success' => false, 'error' => 'Filename required']);
        $filename = basename($filename);
        $oldPath = $templatesDir . $filename;
        
        if (!file_exists($oldPath)) send_json_response(['success' => false, 'error' => 'File not found']);
        
        $isHidden = (strpos($filename, '_hidden_') === 0);
        
        if ($isHidden) {
            // UNHIDE: Remove _hidden_ prefix
            $newFilename = substr($filename, 8); // strlen('_hidden_') = 8
        } else {
            // HIDE: Add _hidden_ prefix
            $newFilename = '_hidden_' . $filename;
        }
        
        $newPath = $templatesDir . $newFilename;
        if (rename($oldPath, $newPath)) {
            send_json_response(['success' => true, 'new_name' => $newFilename, 'visible' => $isHidden]); // visible is now true if was hidden
        } else {
             send_json_response(['success' => false, 'error' => 'Toggle failed']);
        }
    }

    if ($action === 'get') {
        $filename = $_GET['filename'] ?? '';
        $filename = basename($filename); // Security
        $targetPath = $templatesDir . $filename;
        
        if (file_exists($targetPath)) {
             // Clear existing JSON header and any buffered output
            if (ob_get_length()) ob_clean();
            header("Content-Type: image/svg+xml");
            // Disable caching to ensure fresh load
            header("Cache-Control: no-cache, no-store, must-revalidate");
            echo file_get_contents($targetPath);
            exit;
        } else {
             http_response_code(404);
             echo "File not found";
             exit;
        }
    }

    if ($action === 'upload') {
        if (!isset($_FILES['file'])) send_json_response(['success' => false, 'error' => 'No file received']);

        $file = $_FILES['file'];
        if ($file['error'] !== UPLOAD_ERR_OK) {
             throw new Exception("Upload Error Code: " . $file['error']);
        }

        $originalName = pathinfo($file['name'], PATHINFO_FILENAME);
        $customName = $_POST['name'] ?? $originalName;
        $customName = trim($customName);
        if (empty($customName)) $customName = $originalName;
        
        $safeName = preg_replace('/[^a-zA-Z0-9 _-]/', '', $customName);
        if (empty($safeName)) $safeName = "template_" . time();
        $filename = $safeName . '.svg';
        $targetPath = $templatesDir . $filename;
        
        $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
        if ($ext !== 'svg') send_json_response(['success' => false, 'error' => 'Only SVG files allowed']);

        // Check if writable
        if (!is_writable($templatesDir) && !is_writable(dirname($templatesDir))) {
             throw new Exception("Server folder not writable. Permissions needed for: " . $templatesDir);
        }

        if (move_uploaded_file($file['tmp_name'], $targetPath)) {
            send_json_response(['success' => true, 'file' => $filename]);
        } else {
            $last = error_get_last();
            throw new Exception("Move failed. " . ($last['message'] ?? ''));
        }
    }

    if ($action === 'delete') {
        // ... (existing delete logic) ...
        // Simplified for brevity in this replace, ensuring json response
        $input = json_decode(file_get_contents('php://input'), true);
        $filename = $input['filename'] ?? $_POST['filename'] ?? '';
        if (!$filename) send_json_response(['success' => false, 'error' => 'Filename required']);
        $targetPath = $templatesDir . basename($filename);
        if (file_exists($targetPath)) {
            unlink($targetPath) ? send_json_response(['success' => true]) : send_json_response(['success' => false, 'error' => 'Delete failed']);
        }
        send_json_response(['success' => false, 'error' => 'File not found']);
    }

    send_json_response(['success' => false, 'error' => 'Invalid action']);

} catch (Throwable $t) {
    send_json_response(['success' => false, 'error' => $t->getMessage()]);
}
?>
