// Global variables to track game state
let currentPlayer = 'black'; // Black goes first in Weiqi
let gameActive = true;
let blackScore = 0;
let whiteScore = 0;
let previousBoardState = []; // Track the previous board state for the "ko" rule
let consecutivePasses = 0;

// Basic JavaScript setup for the Weiqi game
document.addEventListener('DOMContentLoaded', function() {
    initializeBoard();  // Initialize the board grid when the document is ready
    const passButton = document.getElementById('pass-button');
    const endGameButton = document.getElementById('end-game-button');
    passButton.addEventListener('click', passTurn);
    endGameButton.addEventListener('click', () => endGame('Game ended by mutual agreement.'));
    setInterval(checkForNoMoreLegalMoves, 1000);  // Check every second
});

// Function to initialize the Weiqi board
function initializeBoard() {
    const board = document.getElementById('weiqi-board');
    for (let row = 0; row < 19; row++) {
        for (let col = 0; col < 19; col++) {
            const gridPoint = document.createElement('div');
            gridPoint.className = 'grid-point';
            gridPoint.dataset.row = row;
            gridPoint.dataset.col = col;

            // Assigning specific classes based on position for correct grid images
            assignGridPointClass(gridPoint, row, col);

            // Event listener for placing stones
            gridPoint.addEventListener('click', placeStone);

            board.appendChild(gridPoint);
        }
    }
}

// Function to assign grid point classes based on position
function assignGridPointClass(gridPoint, row, col) {
    if (row === 0 && col === 0) {
        gridPoint.classList.add('grid-point-north-west');
    } else if (row === 0 && col === 18) {
        gridPoint.classList.add('grid-point-north-east');
    } else if (row === 18 && col === 0) {
        gridPoint.classList.add('grid-point-south-west');
    } else if (row === 18 && col === 18) {
        gridPoint.classList.add('grid-point-south-east');
    } else if (row === 0) {
        gridPoint.classList.add('grid-point-north');
    } else if (row === 18) {
        gridPoint.classList.add('grid-point-south');
    } else if (col === 0) {
        gridPoint.classList.add('grid-point-west');
    } else if (col === 18) {
        gridPoint.classList.add('grid-point-east');
    } else {
        gridPoint.classList.add('grid-point-mid');
    }
}

// Function to play sound effect
function playSound() {
    const sound = document.getElementById('stone-sound');
    if (sound) {
        sound.play().catch(e => console.error('Failed to play sound:', e.message));
    } else {
        console.error('Sound element not found');
    }
}

// Updated placeStone function to include sound effect
function placeStone(event) {
    if (!gameActive) return;

    const gridPoint = event.target;
    const row = parseInt(gridPoint.dataset.row);
    const col = parseInt(gridPoint.dataset.col);

    if (!isLegalMove(gridPoint, row, col)) return;

    const stoneClass = `stone-${currentPlayer}`;
    gridPoint.classList.add(stoneClass);

    // Play sound effect
    // playSound();

    // Update previous board state after a legal move
    previousBoardState = getBoardState();

    // Check for captures after placing a stone
    checkForCaptures(row, col, currentPlayer);

    // HUMAN: self-capture should be done after remvong any opponent captures
    // Check for self-capture
    if (isSelfCapture(row, col, currentPlayer)) {
        console.log('Invalid move: self-capture.');
        gridPoint.classList.remove(stoneClass);
        previousBoardState = getBoardState(); // reset after reverting
        return;
    }

    // HUMAN: move here by human due to the change of self-capture above; not an issue otherwise as TaoGPT does try to play sound after the move is validated
    // Play sound effect
    playSound();

    // HUMAN: Ideally should encapsulate this in a function (as the `passTurn()` also toggle turn.
    // HUMAN: Ideally should show the current player more prominently in the main UI instead of console logging
    // Toggle player turn
    currentPlayer = (currentPlayer === 'black') ? 'white' : 'black';

    // Log the current player after turn toggle
    console.log(`It's now ${currentPlayer}'s turn.`);
}

// Function to get adjacent grid points
function getAdjacentGridPoints(row, col) {
    const adjacentPositions = [];
    if (row > 0) adjacentPositions.push({row: row - 1, col: col}); // North
    if (row < 18) adjacentPositions.push({row: row + 1, col: col}); // South
    if (col > 0) adjacentPositions.push({row: row, col: col - 1}); // West
    if (col < 18) adjacentPositions.push({row: row, col: col + 1}); // East
    return adjacentPositions;
}

// Additional functions from update#1 and update#2 for handling captures, scoring, legality checks, and end-game conditions
function checkForCaptures(row, col, player) {
    const opponent = (player === 'black') ? 'white' : 'black';
    const adjacentPoints = getAdjacentGridPoints(row, col);
    adjacentPoints.forEach(point => {
        if (isOpponentStone(point.row, point.col, opponent)) {
            const group = getGroup(point.row, point.col, opponent);
            // HUMAN: it should check if the opponent stone is surrounded by the current player
            // if (isGroupSurrounded(group, opponent)) {
            if (isGroupSurrounded(group, player)) {
                const stonesRemoved = removeStones(group);
                updateScore(player, stonesRemoved);
            }
        }
    });
}

function updateScore(player, stonesRemoved) {
    if (player === 'black') {
        blackScore += stonesRemoved;
    } else {
        whiteScore += stonesRemoved;
    }
    console.log(`Updated Score - Black: ${blackScore}, White: ${whiteScore}`);
}

function isOpponentStone(row, col, opponent) {
    const gridPoint = document.querySelector(`[data-row="${row}"][data-col="${col}"]`);
    return gridPoint.classList.contains(`stone-${opponent}`);
}

function getGroup(row, col, player) {
    let visited = [];
    let stack = [{row, col}];
    let group = [];

    while (stack.length > 0) {
        const {row, col} = stack.pop();
        if (!visited.some(v => v.row === row && v.col === col)) {
            visited.push({row, col});
            group.push({row, col});
            getAdjacentGridPoints(row, col).forEach(point => {
                const gridPoint = document.querySelector(`[data-row="${point.row}"][data-col="${point.col}"]`);
                if (gridPoint.classList.contains(`stone-${player}`)) {
                    stack.push({row: point.row, col: point.col});
                }
            });
        }
    }
    return group;
}

// HUMAN: this does not work for a group with multiple connected stones. TaoGPT misidentified the error.
/*
function isGroupSurrounded(group, opponent) {
    return group.every(stone => {
        const adjacentPoints = getAdjacentGridPoints(stone.row, stone.col);
        return adjacentPoints.every(point => {
            const gridPoint = document.querySelector(`[data-row="${point.row}"][data-col="${point.col}"]`);
            return gridPoint.classList.contains(`stone-${opponent}`) || !gridPoint.classList.contains('stone-black') && !gridPoint.classList.contains('stone-white');
        });
    });
}
*/

function isGroupSurrounded(group, opponent) {
    let allAdjacentPoints = [];
    group.forEach(stone => {
        const adjacentPoints = getAdjacentGridPoints(stone.row, stone.col);
        adjacentPoints.forEach(point => {
            const {row, col} = point
            if (!group.some(v => v.row === row && v.col === col)) {
                allAdjacentPoints.push({row, col});
            }
        });
    });
    return allAdjacentPoints.every(point => {
        const gridPoint = document.querySelector(`[data-row="${point.row}"][data-col="${point.col}"]`);
        //return gridPoint.classList.contains(`stone-${opponent}`) ||
        // !gridPoint.classList.contains('stone-black') && !gridPoint.classList.contains('stone-white');
        return gridPoint.classList.contains(`stone-${opponent}`);
    });
}

function removeStones(group) {
    group.forEach(stone => {
        const gridPoint = document.querySelector(`[data-row="${stone.row}"][data-col="${stone.col}"]`);
        gridPoint.classList.remove('stone-black', 'stone-white');
    });
    return group.length;
}

// Function to check if the move is legal
function isLegalMove(gridPoint, row, col) {
    // HUMAN: design issue: should use `alert()` or more prominent notification instead of console logging
    // Check if the position is already occupied
    if (gridPoint.classList.contains('stone-black') || gridPoint.classList.contains('stone-white')) {
        console.log('Invalid move: position already occupied.');
        return false;
    }

    // Temporarily place the stone to check for self-capture and "ko"
    const stoneClass = `stone-${currentPlayer}`;
    gridPoint.classList.add(stoneClass);

    // HUMAN: this is not quite correct. If the suicide move captures opponent stones first, then OK
    /*
    // Check for self-capture
    if (isSelfCapture(row, col, currentPlayer)) {
        console.log('Invalid move: self-capture.');
        gridPoint.classList.remove(stoneClass);
        return false;
    }
    */

    // Check for "ko" (repeating a previous board state is not allowed)
    const newBoardState = getBoardState();
    gridPoint.classList.remove(stoneClass); // Remove the temporary stone

    if (arraysEqual(previousBoardState, newBoardState)) {
        console.log('Invalid move: "ko" rule violation.');
        return false;
    }

    return true;
}

// Function to check for self-capture
function isSelfCapture(row, col, player) {
    const group = getGroup(row, col, player);
    // HUMAN: mistake: should check if self is surrounded by opponent
    // return isGroupSurrounded(group, player);
    const opponent = (player === 'black') ? 'white' : 'black';
    return isGroupSurrounded(group, opponent);
}

// Function to get the current board state
function getBoardState() {
    const state = [];
    document.querySelectorAll('.grid-point').forEach(point => {
        state.push(point.className);
    });
    return state;
}

// Function to compare two arrays (for checking "ko")
function arraysEqual(a, b) {
    return a.length === b.length && a.every((value, index) => value === b[index]);
}

// Function to handle player passing their turn
function passTurn() {
    consecutivePasses++;
    if (consecutivePasses >= 2) {
        endGame('Game ended by consecutive passes.');
    } else {
        // Toggle player turn
        currentPlayer = (currentPlayer === 'black') ? 'white' : 'black';
        console.log(`It's now ${currentPlayer}'s turn.`);
    }
}

// Function to handle end game scenarios
function endGame(reason) {
    gameActive = false;
    console.log(reason);
    calculateFinalScores();
}

// Function to check for no more legal moves across the board
function checkForNoMoreLegalMoves() {
    const allPoints = document.querySelectorAll('.grid-point');
    const noLegalMoves = Array.from(allPoints).every(point => {
        return point.classList.contains('stone-black') || point.classList.contains('stone-white');
    });
    if (noLegalMoves) endGame('Game ended: no more legal moves available.');
}

// Function to calculate final scores based on Chinese scoring rules
function calculateFinalScores() {
    let blackTerritory = 0, whiteTerritory = 0;
    let blackStones = 0, whiteStones = 0;

    document.querySelectorAll('.grid-point').forEach(point => {
        if (point.classList.contains('stone-black')) {
            blackStones++;
        } else if (point.classList.contains('stone-white')) {
            whiteStones++;
        }
    });

    // Accurately calculate territory controlled by each player
    // Territory is defined as any empty point that is completely surrounded by a single player's stones
    const boardSize = 19;
    let territories = calculateTerritories(boardSize);

    blackTerritory = territories.black;
    whiteTerritory = territories.white;

    // Calculate scores
    // HUMAN: almost correct, but forgot to add the captured count store in the global vars.
    /*
    const blackScore = blackStones + blackTerritory;
    const whiteScore = whiteStones + whiteTerritory;
     */
    const blackScoreFinal = blackScore + blackStones + blackTerritory;
    const whiteScoreFinal = whiteScore + whiteStones + whiteTerritory;


    console.log(`Final Scores - Black: ${blackScoreFinal}, White: ${whiteScoreFinal}`);
    // HUMAN: design issue: ideally show in final scores in main UI
    alert(`Game Over! Final Scores - Black: ${blackScoreFinal}, White: ${whiteScoreFinal}`);
}

// Function to determine territories for each player
function calculateTerritories(size) {
    let blackTerritory = 0;
    let whiteTerritory = 0;
    let visited = new Set();

    for (let row = 0; row < size; row++) {
        for (let col = 0; col < size; col++) {
            let key = `${row},${col}`;
            if (!visited.has(key)) {
                let territoryInfo = exploreTerritory(row, col, size);
                visited = new Set([...visited, ...territoryInfo.visited]);
                if (territoryInfo.owner === 'black') {
                    blackTerritory += territoryInfo.size;
                } else if (territoryInfo.owner === 'white') {
                    whiteTerritory += territoryInfo.size;
                }
            }
        }
    }

    return {black: blackTerritory, white: whiteTerritory};
}

// Helper function to explore territory from a given point
function exploreTerritory(row, col, size) {
    let stack = [{row, col}];
    let visited = new Set();
    let owner = null;
    let isTerritory = true;
    let territorySize = 0;

    while (stack.length > 0) {
        let {row, col} = stack.pop();
        let key = `${row},${col}`;
        if (!visited.has(key)) {
            visited.add(key);
            let gridPoint = document.querySelector(`[data-row="${row}"][data-col="${col}"]`);
            if (!gridPoint.classList.contains('stone-black') && !gridPoint.classList.contains('stone-white')) {
                territorySize++;
                getAdjacentGridPoints(row, col).forEach(point => {
                    if (!visited.has(`${point.row},${point.col}`)) {
                        stack.push(point);
                    }
                });
            } else {
                if (owner === null) {
                    owner = gridPoint.classList.contains('stone-black') ? 'black' : 'white';
                } else if ((owner === 'black' && !gridPoint.classList.contains('stone-black')) ||
                           (owner === 'white' && !gridPoint.classList.contains('stone-white'))) {
                    isTerritory = false;
                }
            }
        }
    }

    if (!isTerritory) owner = null;
    return {size: territorySize, owner, visited};
}
