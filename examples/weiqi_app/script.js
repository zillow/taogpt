// Constants for the board size and initial player
const BOARD_SIZE = 19;
const BLACK = 'black';
const WHITE = 'white';

// Game state variables
let board = [];
let currentPlayer = BLACK;
let blackCaptures = 0;
let whiteCaptures = 0;
let gameEnded = false;

// History to track board states for the rule of Ko
let history = [];

// Variables to track consecutive passes
let consecutivePasses = 0;

// Global variables to store the scores
let blackScore = 0;
let whiteScore = 0;

// Initialize the game board as a 19x19 grid of null values
function initializeBoard() {
    for (let i = 0; i < BOARD_SIZE; i++) {
        board[i] = [];
        for (let j = 0; j < BOARD_SIZE; j++) {
            board[i][j] = null;
        }
    }
}

// Set up the initial game state
function setupGame() {
    initializeBoard();
    currentPlayer = BLACK; // Black plays first
    blackCaptures = 0;
    whiteCaptures = 0;
    gameEnded = false;
    history = []; // Clear history for the rule of Ko
    consecutivePasses = 0; // Reset consecutive passes
    updateUI();
}

// Function to convert board state to a string for history tracking
function boardToString(tempBoard = board) {
    return tempBoard.map(row => row.map(cell => cell || '0').join('')).join(';');
}

// Function to check if a move violates the rule of Ko
function violatesKo(row, col, player) {
    // Simulate the move on a temporary board
    let tempBoard = JSON.parse(JSON.stringify(board));
    tempBoard[row][col] = player;
    checkAndHandleCaptures(row, col, player, tempBoard); // Simulate captures as well
    let tempBoardString = boardToString(tempBoard);

    // Check if this board state has occurred before
    return history.includes(tempBoardString);
}

// Function to check for self-capture
function isSelfCapture(row, col, player) {
    // HUMAN: forget to check if opponent stones are captured before suicidal move.
    let tempBoard = JSON.parse(JSON.stringify(board));

    // Temporarily place the stone on the board
    board[row][col] = player;
    checkAndHandleCaptures(row, col, player, board); // added by human
    board[row][col] = player;
    // Check for liberties after placing the stone
    const captured = countLiberties(row, col) === 0;
    // Restore the position to its original state
    board[row][col] = null;

    // by human: restore for the above fix
    board = tempBoard
    return captured;
}

// Updated handlePlayerMove function with comprehensive checks
function handlePlayerMove(row, col) {
    if (board[row][col] !== null) {
        // HUMAN: (warning) design issue: should show an alert() instead of printing on console; same below
        // console.log("Invalid move: position is already occupied.");
        alert("Invalid move: position is already occupied.");
        return; // Prevent placing a stone on an occupied spot
    }

    // Check for Ko violation
    if (violatesKo(row, col, currentPlayer)) {
        // console.log("Move violates the rule of Ko.");
        alert("Move violates the rule of Ko.");
        return;
    }

    // Check for self-capture
    if (isSelfCapture(row, col, currentPlayer)) {
        // console.log("Invalid move: results in self-capture.");
        alert("Invalid move: results in self-capture.");
        return;
    }

    // Place the stone on the board
    board[row][col] = currentPlayer;

    // Check for captures and handle them
    // by human: modified according to issue in checkAndHandleCaptures()
    let captures = checkAndHandleCaptures(row, col, currentPlayer);
    blackCaptures += captures.blackCaptures;
    whiteCaptures += captures.whiteCaptures

    // Add current board state to history
    history.push(boardToString());

    // Reset consecutive passes on a valid move
    consecutivePasses = 0;

    // Switch the current player
    currentPlayer = (currentPlayer === BLACK) ? WHITE : BLACK;

    // Update the UI to reflect the move
    calculateFinalScore();
    updateUI();
}

// Helper function to check if a specific position is on the board
function isOnBoard(x, y) {
    return x >= 0 && x < BOARD_SIZE && y >= 0 && y < BOARD_SIZE;
}

// Function to count liberties of a group of stones
function countLiberties(x, y, visited = {}) {
    const key = x + ',' + y;
    if (visited[key]) {
        return 0;
    }
    visited[key] = true;

    let liberties = 0;
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]]; // Up, Down, Left, Right
    for (let [dx, dy] of directions) {
        const nx = x + dx, ny = y + dy;
        if (isOnBoard(nx, ny)) {
            if (board[nx][ny] === null) {
                liberties++;
            } else if (board[nx][ny] === board[x][y]) {
                liberties += countLiberties(nx, ny, visited);
            }
        }
    }
    return liberties;
}

// Function to remove stones from the board
function removeStones(stones) {
    for (let [x, y] of stones) {
        board[x][y] = null;
        // HUMAN: should be opposite. the `*Captures` identifies who captures how many stones, not lost how many.
        // currentPlayer === BLACK ? whiteCaptures++ : blackCaptures++;
        currentPlayer === BLACK ? blackCaptures++ : whiteCaptures++;
    }
}

// Updated function to check and handle captures
function checkAndHandleCaptures(row, col, player, tempBoard = board) {
    const opponent = player === BLACK ? WHITE : BLACK;
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]]; // Up, Down, Left, Right
    // HUMAN: should be a set to avoid duplicated counts
    // let capturedGroups = [];
    let capturedGroups = new Set();

    for (let [dx, dy] of directions) {
        const nx = row + dx, ny = col + dy;
        if (isOnBoard(nx, ny) && tempBoard[nx][ny] === opponent) {
            const visited = {};
            if (countLiberties(nx, ny, visited) === 0) {
                // by human: rewrite in accordance to change above
                for (let key of Object.keys(visited).map(key => key.split(',').map(Number))) {
                    capturedGroups.add(key);
                }
            }
        }
    }

    /* HUMAN: this function is used to simulate move and check for violations but `removeStone()` mutate global states
    if (capturedGroups.length > 0) {
        removeStones(capturedGroups);
    }
    */
    let whiteCaptures = 0, blackCaptures = 0;
    for (let [x, y] of capturedGroups) {
        tempBoard[x][y] = null;
        currentPlayer === BLACK ? blackCaptures++ : whiteCaptures++;
    }
    return {blackCaptures, whiteCaptures};
}

// Function to handle player pass
function handlePlayerPass() {
    consecutivePasses += 1;
    if (consecutivePasses >= 2) {
        gameEnded = true;
        console.log("Game ended: Both players passed consecutively.");
        calculateFinalScore();
    } else {
        // Switch the current player
        currentPlayer = (currentPlayer === BLACK) ? WHITE : BLACK;
        updateUI();
    }
}

// Function to calculate territory for each player
function calculateTerritory() {
    let blackTerritory = 0;
    let whiteTerritory = 0;
    let visited = new Set();

    function explore(x, y) {
        const key = `${x},${y}`;
        if (visited.has(key) || !isOnBoard(x, y) || board[x][y] !== null) return null;
        visited.add(key);

        let owner = null;
        const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]]; // Up, Down, Left, Right
        for (let [dx, dy] of directions) {
            const nx = x + dx, ny = y + dy;
            if (isOnBoard(nx, ny)) {
                if (board[nx][ny] === null) {
                    if (!visited.has(`${nx},${ny}`)) {
                        const result = explore(nx, ny);
                        if (result === null) {
                            // HUMAN: should not do anything in this case
                            // owner = null;
                            // break;
                        } else if (owner === null) {
                            owner = result;
                        } else if (owner !== result) {
                            // HUMAN: must use a marker to mark territories belonging to both; same below
                            // owner = null;
                            owner = 'both';
                            break;
                        }
                    }
                } else {
                    if (owner === null) {
                        owner = board[nx][ny];
                    } else if (owner !== board[nx][ny]) {
                        // owner = null;
                        owner = 'both'; // by human: fix as above
                        break;
                    }
                }
            }
        }
        return owner;
    }

    for (let i = 0; i < BOARD_SIZE; i++) {
        for (let j = 0; j < BOARD_SIZE; j++) {
            if (board[i][j] === null && !visited.has(`${i},${j}`)) {
                const owner = explore(i, j);
                if (owner === BLACK) blackTerritory++;
                else if (owner === WHITE) whiteTerritory++;
                // HUMAN: given this algorithm, must clear the `visited`
                visited.clear();
            }
        }
    }

    console.log(`Black Territory: ${blackTerritory}, White Territory: ${whiteTerritory}`);
    return { blackTerritory, whiteTerritory };
}

// Ensure the calculateFinalScore function updates the global score variables and calls updateUI afterward
function calculateFinalScore() {
    // HUMAN: (warning) should reset the scores for robustness (or better yet avoid using global vars)
    blackScore = 0;
    whiteScore = 0;
    const { blackTerritory, whiteTerritory } = calculateTerritory();
    // HUMAN: stones are counted toward scores in Chinese rule; missing
    let blackStones = 0, whiteStones = 0
    for (let i = 0; i < BOARD_SIZE; i++) {
        for (let j = 0; j < BOARD_SIZE; j++) {
            if (board[i][j] === BLACK) {
                blackStones++;
            } else if (board[i][j] === WHITE) {
                whiteStones++;
            }
        }
    }
    blackScore = blackTerritory + blackCaptures + blackStones;
    whiteScore = whiteTerritory + whiteCaptures + whiteStones;
    console.log(`Final Score - Black: ${blackScore}, White: ${whiteScore}`);
    // HUMAN: (warning) bad programming practice. should separate the score calc from UI update
    updateUI(); // Call updateUI to display scores after they are calculated
}

// Event listener for player interactions on the board
document.getElementById('weiqi-board').addEventListener('click', function(event) {
    let target = event.target;
    let row = parseInt(target.getAttribute('data-row'));
    let col = parseInt(target.getAttribute('data-col'));

    if (target.tagName === 'DIV' && target.parentNode.id === 'weiqi-board') {
        handlePlayerMove(row, col);
    }
});

// HUMAN: missing pass button and event handler call; added by human
document.getElementById('pass-button').addEventListener('click', function(event) {
    handlePlayerPass()
});

// Function to update the UI with final scores and restart option
function updateUI() {
    const boardElement = document.getElementById('weiqi-board');
    boardElement.innerHTML = ''; // Clear the board UI

    // Re-render the board with the current state
    for (let i = 0; i < BOARD_SIZE; i++) {
        for (let j = 0; j < BOARD_SIZE; j++) {
            let cell = document.createElement('div');
            cell.setAttribute('data-row', i);
            cell.setAttribute('data-col', j);
            cell.style.backgroundImage = board[i][j] ? `url('assets/${board[i][j]}_stone.png')` : '';
            boardElement.appendChild(cell);
        }
    }

    // Display final scores if the game has ended
    if (gameEnded) {
        // HUMAN: (warning) works but looks a bit ugly.
        const scoreBoard = document.createElement('div');
        scoreBoard.innerHTML = `<p>Game Over</p><p>Black Score: ${blackScore}</p><p>White Score: ${whiteScore}</p>`;
        boardElement.appendChild(scoreBoard);

        // Add a button to restart the game
        const restartButton = document.createElement('button');
        restartButton.textContent = 'Restart Game';
        restartButton.onclick = setupGame;
        boardElement.appendChild(restartButton);
    }

    console.log("Board updated. Current player: " + currentPlayer);
    // HUMAN: (warning) design issue: show current player in the UI (though this can be considered optional)
    const current_span = document.createElement('current-player');
    current_span.textContent = currentPlayer
}

// Call setupGame to initialize the game when the script loads
setupGame();
