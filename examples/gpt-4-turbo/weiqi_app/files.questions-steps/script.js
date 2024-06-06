// Constants for the board size and players
const BOARD_SIZE = 19;
const EMPTY = 0;
const BLACK = 1;
const WHITE = 2;

// Initialize the game state
let board = [];
for (let i = 0; i < BOARD_SIZE; i++) {
    board[i] = [];
    for (let j = 0; j < BOARD_SIZE; j++) {
        board[i][j] = EMPTY;
    }
}

// Variable to track the current player (Black starts first)
let currentPlayer = BLACK;

// Variable to track the last move to check for consecutive passes
let lastMoveWasPass = false;

// Function to switch the current player
function switchPlayer() {
    currentPlayer = (currentPlayer === BLACK) ? WHITE : BLACK;
}

// Function to initialize the board with event listeners
function initializeBoard() {
    const boardElement = document.getElementById('weiqi-board');
    for (let i = 0; i < BOARD_SIZE; i++) {
        for (let j = 0; j < BOARD_SIZE; j++) {
            const cell = document.createElement('div');
            cell.className = 'grid-point';
            cell.dataset.row = i;
            cell.dataset.col = j;
            cell.addEventListener('click', handleCellClick);
            boardElement.appendChild(cell);
        }
    }
}

// Handle cell click to place a stone
function handleCellClick(event) {
    const row = parseInt(event.target.dataset.row, 10);
    const col = parseInt(event.target.dataset.col, 10);
    if (isMoveLegal(row, col)) {
        board[row][col] = currentPlayer; // Place the stone
        event.target.classList.add(currentPlayer === BLACK ? 'stone black' : 'stone white');
        checkAndRemoveCaptures(row, col); // Check for captures
        updateUI(); // Update the UI to reflect the new board state
        updateMoveHistoryAndCheckEnd(false); // Update move history with a non-pass move
        switchPlayer(); // Switch the turn to the other player
    } else {
        // Handle pass move
        updateMoveHistoryAndCheckEnd(true); // Update move history with a pass move
        switchPlayer(); // Switch the turn to the other player
    }
}

// Function to update the move history and check for game end
function updateMoveHistoryAndCheckEnd(pass) {
    if (pass && lastMoveWasPass) {
        calculateScores(); // Calculate scores and end the game
    }
    lastMoveWasPass = pass; // Update the last move status
}

// Function to calculate and display the scores using Chinese rules
function calculateScores() {
    let blackScore = 0, whiteScore = 0;
    let visited = Array.from({ length: BOARD_SIZE }, () => Array(BOARD_SIZE).fill(false));

    // Count stones directly on the board
    board.forEach((row, i) => {
        row.forEach((cell, j) => {
            if (cell === BLACK) blackScore++;
            if (cell === WHITE) whiteScore++;
            if (cell === EMPTY && !visited[i][j]) {
                // Count territory using flood fill to determine surrounded area
                const territory = countTerritory(i, j, visited);
                if (territory.owner === BLACK) blackScore += territory.count;
                if (territory.owner === WHITE) whiteScore += territory.count;
            }
        });
    });

    // Call displayEndGame to update the UI
    displayEndGame(blackScore, whiteScore);
}

// Function to count territory using flood fill
function countTerritory(row, col, visited) {
    let count = 0;
    let owner = null;
    let stack = [[row, col]];
    let directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];

    while (stack.length > 0) {
        let [r, c] = stack.pop();
        if (visited[r][c]) continue;
        visited[r][c] = true;
        count++;
        let currentOwner = board[r][c];

        if (currentOwner !== EMPTY) {
            if (owner === null) owner = currentOwner;
            else if (owner !== currentOwner) owner = null; // Mixed territory
        }

        directions.forEach(([dr, dc]) => {
            let newRow = r + dr, newCol = c + dc;
            if (newRow >= 0 && newRow < BOARD_SIZE && newCol >= 0 && newCol < BOARD_SIZE && !visited[newRow][newCol] && board[newRow][newCol] !== (owner === BLACK ? WHITE : BLACK)) {
                stack.push([newRow, newCol]);
            }
        });
    }

    return { count, owner };
}

// Function to display the final scores and end the game visually
function displayEndGame(blackScore, whiteScore) {
    const boardElement = document.getElementById('weiqi-board');
    const scoreElement = document.createElement('div');
    scoreElement.id = 'final-scores';
    scoreElement.innerHTML = `<h1>Game Over!</h1><p>Final scores - Black: ${blackScore}, White: ${whiteScore}</p>`;
    boardElement.appendChild(scoreElement);

    // Optionally, disable the board to prevent further interaction
    boardElement.removeEventListener('click', handleCellClick);
    boardElement.style.opacity = '0.5'; // Dim the board to indicate the game is over
}

// Initialize and update the board UI when the document is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeBoard();
    updateUI();
});

/********************* HUMAN REVIEW: these functions are lost during file consolidation **********************/

// Function to check and remove captures around a newly placed stone
function checkAndRemoveCaptures(row, col) {
    const opponent = (currentPlayer === BLACK) ? WHITE : BLACK;
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    directions.forEach(([dr, dc]) => {
        const newRow = row + dr, newCol = col + dc;
        if (newRow >= 0 && newRow < BOARD_SIZE && newCol >= 0 && newCol < BOARD_SIZE && board[newRow][newCol] === opponent) {
            if (!hasLiberties(newRow, newCol)) {
                removeStones(newRow, newCol);
            }
        }
    });
}

// Function to recursively remove stones from the board
function removeStones(row, col) {
    const stoneColor = board[row][col];
    board[row][col] = EMPTY; // Remove the stone
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    directions.forEach(([dr, dc]) => {
        const newRow = row + dr, newCol = col + dc;
        if (newRow >= 0 && newRow < BOARD_SIZE && newCol >= 0 && newCol < BOARD_SIZE && board[newRow][newCol] === stoneColor) {
            removeStones(newRow, newCol); // Recursively remove connected stones
        }
    });
}
