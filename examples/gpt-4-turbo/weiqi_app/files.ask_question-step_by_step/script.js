document.addEventListener('DOMContentLoaded', function() {
    const gameContainer = document.getElementById('game-container');
    const resetButton = document.getElementById('reset-button');
    const scoreDisplay = document.getElementById('score-display');
    const board = document.createElement('div');
    board.className = 'board';
    const boardSize = 19;
    let currentPlayer = 'black';
    let boardState = Array(boardSize).fill().map(() => Array(boardSize).fill(null));

    // Generate a 19x19 grid
    for (let i = 0; i < boardSize; i++) {
        for (let j = 0; j < boardSize; j++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.row = i;
            cell.dataset.col = j;
            cell.addEventListener('click', function() {
                placeStone(this, i, j);
            });
            board.appendChild(cell);
        }
    }

    gameContainer.appendChild(board);
    resetButton.addEventListener('click', resetGame);

    function placeStone(cell, row, col) {
        if (!boardState[row][col]) {
            boardState[row][col] = currentPlayer;
            cell.classList.add(currentPlayer === 'black' ? 'black-stone' : 'white-stone');
            togglePlayer();
            updateScore();
        }
    }

    function togglePlayer() {
        currentPlayer = currentPlayer === 'black' ? 'white' : 'black';
    }

    function updateScore() {
        const { blackStones, whiteStones } = countStones();
        const { blackTerritory, whiteTerritory } = calculateTerritories();

        const blackScore = blackStones + blackTerritory;
        const whiteScore = whiteStones + whiteTerritory;

        scoreDisplay.textContent = `Black: ${blackScore} | White: ${whiteScore}`;
    }

    function countStones() {
        let blackStones = 0;
        let whiteStones = 0;
        for (let row of boardState) {
            for (let cell of row) {
                if (cell === 'black') {
                    blackStones++;
                } else if (cell === 'white') {
                    whiteStones++;
                }
            }
        }
        return { blackStones, whiteStones };
    }

    function calculateTerritories() {
        const visited = Array(boardSize).fill().map(() => Array(boardSize).fill(false));
        let blackTerritory = 0;
        let whiteTerritory = 0;

        function floodFill(row, col, color) {
            if (row < 0 || col < 0 || row >= boardSize || col >= boardSize || visited[row][col]) {
                return true;
            }
            if (boardState[row][col] === null) {
                visited[row][col] = true;
                const results = [
                    floodFill(row + 1, col, color),
                    floodFill(row - 1, col, color),
                    floodFill(row, col + 1, color),
                    floodFill(row, col - 1, color)
                ];
                return results.every(res => res);
            }
            return boardState[row][col] === color;
        }

        for (let i = 0; i < boardSize; i++) {
            for (let j = 0; j < boardSize; j++) {
                if (boardState[i][j] === null && !visited[i][j]) {
                    if (floodFill(i, j, 'black')) {
                        blackTerritory++;
                    }
                    visited[i][j] = false; // Reset visited for the next flood fill
                    if (floodFill(i, j, 'white')) {
                        whiteTerritory++;
                    }
                }
            }
        }

        return { blackTerritory, whiteTerritory };
    }

    function resetGame() {
        boardState = Array(boardSize).fill().map(() => Array(boardSize).fill(null));
        currentPlayer = 'black';
        scoreDisplay.textContent = 'Black: 0 | White: 0';
        document.querySelectorAll('.cell').forEach(cell => {
            cell.className = 'cell';
        });
    }
});