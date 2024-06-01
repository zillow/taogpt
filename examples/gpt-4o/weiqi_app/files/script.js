const boardSize = 19; // Assuming a 19x19 board
let currentPlayer = 'black'; // Black always starts first
let boardState = Array(boardSize).fill().map(() => Array(boardSize).fill(null)); // Initialize an empty board
let capturedStones = { black: 0, white: 0 }; // Track captured stones for each player

// Function to initialize the board with empty grid points
function initializeBoard() {
    const boardContainer = document.getElementById('board-container');
    boardContainer.innerHTML = ''; // Clear any existing content

    for (let row = 0; row < boardSize; row++) {
        for (let col = 0; col < boardSize; col++) {
            const gridPoint = document.createElement('div');
            gridPoint.classList.add('grid-point');

            // Determine the appropriate class for the grid point based on its position
            if (row === 0 && col === 0) {
                gridPoint.classList.add('north-west');
            } else if (row === 0 && col === boardSize - 1) {
                gridPoint.classList.add('north-east');
            } else if (row === boardSize - 1 && col === 0) {
                gridPoint.classList.add('south-west');
            } else if (row === boardSize - 1 && col === boardSize - 1) {
                gridPoint.classList.add('south-east');
            } else if (row === 0) {
                gridPoint.classList.add('north');
            } else if (row === boardSize - 1) {
                gridPoint.classList.add('south');
            } else if (col === 0) {
                gridPoint.classList.add('west');
            } else if (col === boardSize - 1) {
                gridPoint.classList.add('east');
            } else {
                gridPoint.classList.add('mid');
            }

            // Set the data attributes for row and column
            gridPoint.dataset.row = row;
            gridPoint.dataset.col = col;

            // Add event listener for placing stones
            gridPoint.addEventListener('click', placeStone);

            boardContainer.appendChild(gridPoint);
        }
    }
}

// Function to switch the current player after each move
function switchPlayer() {
    currentPlayer = currentPlayer === 'black' ? 'white' : 'black';
}

// Function to update the board state when a stone is placed
function placeStone(event) {
    const row = parseInt(event.target.dataset.row);
    const col = parseInt(event.target.dataset.col);

    // Check if the grid point is already occupied
    if (boardState[row][col] !== null) {
        displayMessage("Invalid move! This point is already occupied.");
        return;
    }

    // Update the board state
    boardState[row][col] = currentPlayer;

    // Create a stone element and add it to the grid point
    const stone = document.createElement('div');
    stone.classList.add('stone', currentPlayer);
    event.target.appendChild(stone);

    // Check for captured stones
    checkCapturedStones(row, col);

    // Switch the current player
    switchPlayer();

    // Update the score display
    updateScoreDisplay();
}

// Function to check for captured stones
function checkCapturedStones(row, col) {
    const opponent = currentPlayer === 'black' ? 'white' : 'black';
    const directions = [
        [-1, 0], [1, 0], [0, -1], [0, 1]
    ];

    directions.forEach(([dx, dy]) => {
        const newRow = row + dx;
        const newCol = col + dy;
        if (isOnBoard(newRow, newCol) && boardState[newRow][newCol] === opponent) {
            if (isCaptured(newRow, newCol, opponent)) {
                removeStones(newRow, newCol, opponent);
            }
        }
    });
}

// Function to check if a group of stones is captured
function isCaptured(row, col, player) {
    const visited = Array(boardSize).fill().map(() => Array(boardSize).fill(false));
    return !hasLiberty(row, col, player, visited);
}

// Function to check if a group of stones has any liberties
function hasLiberty(row, col, player, visited) {
    if (!isOnBoard(row, col) || visited[row][col]) return false;
    if (boardState[row][col] === null) return true;
    if (boardState[row][col] !== player) return false;

    visited[row][col] = true;

    return (
        hasLiberty(row - 1, col, player, visited) ||
        hasLiberty(row + 1, col, player, visited) ||
        hasLiberty(row, col - 1, player, visited) ||
        hasLiberty(row, col + 1, player, visited)
    );
}

// Function to remove captured stones from the board
function removeStones(row, col, player) {
    if (!isOnBoard(row, col) || boardState[row][col] !== player) return;

    boardState[row][col] = null;
    const gridPoint = document.querySelector(`.grid-point[data-row="${row}"][data-col="${col}"]`);
    gridPoint.innerHTML = '';

    capturedStones[player]++;
    removeStones(row - 1, col, player);
    removeStones(row + 1, col, player);
    removeStones(row, col - 1, player);
    removeStones(row, col + 1, player);
}

// Function to check if a position is on the board
function isOnBoard(row, col) {
    return row >= 0 && row < boardSize && col >= 0 && col < boardSize;
}

// Function to count the number of stones for each player
function countStones() {
    let blackStones = 0;
    let whiteStones = 0;

    for (let row = 0; row < boardSize; row++) {
        for (let col = 0; col < boardSize; col++) {
            if (boardState[row][col] === 'black') {
                blackStones++;
            } else if (boardState[row][col] === 'white') {
                whiteStones++;
            }
        }
    }

    return { blackStones, whiteStones };
}

// Improved flood fill algorithm to count the number of empty points surrounded by each player
function countSurroundedEmptyPoints() {
    let blackSurroundedPoints = 0;
    let whiteSurroundedPoints = 0;
    let visited = Array(boardSize).fill().map(() => Array(boardSize).fill(false));

    function floodFill(row, col) {
        let queue = [[row, col]];
        let emptyPoints = [];
        let surroundedBy = null;
        let isEdge = false;

        while (queue.length > 0) {
            let [r, c] = queue.shift();
            if (r < 0 || r >= boardSize || c < 0 || c >= boardSize) {
                isEdge = true;
                continue;
            }
            if (visited[r][c]) continue;
            visited[r][c] = true;

            if (boardState[r][c] === null) {
                emptyPoints.push([r, c]);
                queue.push([r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]);
            } else {
                if (surroundedBy === null) {
                    surroundedBy = boardState[r][c];
                } else if (surroundedBy !== boardState[r][c]) {
                    surroundedBy = 'mixed';
                }
            }
        }

        if (!isEdge && surroundedBy === 'black') {
            blackSurroundedPoints += emptyPoints.length;
        } else if (!isEdge && surroundedBy === 'white') {
            whiteSurroundedPoints += emptyPoints.length;
        }
    }

    for (let row = 0; row < boardSize; row++) {
        for (let col = 0; col < boardSize; col++) {
            if (boardState[row][col] === null && !visited[row][col]) {
                floodFill(row, col);
            }
        }
    }

    return { blackSurroundedPoints, whiteSurroundedPoints };
}

// Function to calculate the score for each player
function calculateScore() {
    const { blackStones, whiteStones } = countStones();
    const { blackSurroundedPoints, whiteSurroundedPoints } = countSurroundedEmptyPoints();

    const blackScore = blackStones + blackSurroundedPoints + capturedStones.white;
    const whiteScore = whiteStones + whiteSurroundedPoints + capturedStones.black;

    return { blackScore, whiteScore };
}

// Function to update the score display
function updateScoreDisplay() {
    const { blackScore, whiteScore } = calculateScore();
    document.getElementById('black-score').textContent = `Black: ${blackScore}`;
    document.getElementById('white-score').textContent = `White: ${whiteScore}`;
}

// Function to handle the end game button click event
function handleEndGame() {
    const { blackScore, whiteScore } = calculateScore();
    alert(`Game Over!\nFinal Scores:\nBlack: ${blackScore}\nWhite: ${whiteScore}`);
}

// Function to display messages
function displayMessage(message) {
    const messageDisplay = document.getElementById('message-display');
    messageDisplay.textContent = message;
    setTimeout(() => {
        messageDisplay.textContent = '';
    }, 3000); // Clear the message after 3 seconds
}

// Initialize the board when the page loads
window.onload = () => {
    initializeBoard();
    updateScoreDisplay();
};

// Add event listener for the end game button
document.getElementById('end-game-button').addEventListener('click', handleEndGame);