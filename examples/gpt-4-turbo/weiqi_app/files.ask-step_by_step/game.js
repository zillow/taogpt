document.addEventListener('DOMContentLoaded', function() {
    const board = document.getElementById('board');
    let currentPlayer = 'Black';
    let boardState = Array(19).fill().map(() => Array(19).fill(null));
    let score = { Black: 0, White: 0 };

    function initializeBoard() {
        for (let row = 0; row < 19; row++) {
            for (let col = 0; col < 19; col++) {
                const gridPoint = document.createElement('div');
                gridPoint.className = 'grid-point ' + getGridPointClass(row, col);
                gridPoint.dataset.row = row;
                gridPoint.dataset.col = col;
                board.appendChild(gridPoint);
            }
        }
    }

    function getGridPointClass(row, col) {
        if (row === 0 && col === 0) {
            return 'grid-point-north-west';
        } else if (row === 0 && col === 18) {
            return 'grid-point-north-east';
        } else if (row === 18 && col === 0) {
            return 'grid-point-south-west';
        } else if (row === 18 && col === 18) {
            return 'grid-point-south-east';
        } else if (row === 0) {
            return 'grid-point-north';
        } else if (row === 18) {
            return 'grid-point-south';
        } else if (col === 0) {
            return 'grid-point-west';
        } else if (col === 18) {
            return 'grid-point-east';
        } else {
            return 'grid-point-mid';
        }
    }

    board.addEventListener('click', function(event) {
        const target = event.target;
        if (target.classList.contains('grid-point') && !target.firstChild) {
            placeStone(target);
        }
    });

    function placeStone(gridPoint) {
        const row = parseInt(gridPoint.dataset.row);
        const col = parseInt(gridPoint.dataset.col);
        if (boardState[row][col] === null) {
            const stone = document.createElement('div');
            stone.className = 'stone ' + (currentPlayer === 'Black' ? 'black-stone' : 'white-stone');
            gridPoint.appendChild(stone);
            boardState[row][col] = currentPlayer;
            checkCaptures(row, col, currentPlayer);
            updateScores();
            togglePlayer();
        }
    }

    function checkCaptures(row, col, player) {
        const enemy = player === 'Black' ? 'White' : 'Black';
        const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];
        directions.forEach(([dr, dc]) => {
            const nRow = row + dr;
            const nCol = col + dc;
            if (isValidPosition(nRow, nCol) && boardState[nRow][nCol] === enemy) {
                if (isCaptured(nRow, nCol, enemy)) {
                    removeStones(nRow, nCol, enemy);
                }
            }
        });
    }

    function isValidPosition(row, col) {
        return row >= 0 && row < 19 && col >= 0 && col < 19;
    }

    function isCaptured(row, col, player) {
        const visited = new Set();
        const stack = [[row, col]];
        let hasLiberty = false;

        while (stack.length > 0 && !hasLiberty) {
            const [r, c] = stack.pop();
            visited.add(`${r},${c}`);
            [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(([dr, dc]) => {
                const nr = r + dr;
                const nc = c + dc;
                if (isValidPosition(nr, nc)) {
                    if (boardState[nr][nc] === null) {
                        hasLiberty = true;
                    } else if (boardState[nr][nc] === player && !visited.has(`${nr},${nc}`)) {
                        stack.push([nr, nc]);
                    }
                }
            });
        }
        return !hasLiberty;
    }

    function removeStones(row, col, player) {
        const stack = [[row, col]];
        const toRemove = [];

        while (stack.length > 0) {
            const [r, c] = stack.pop();
            toRemove.push([r, c]);
            [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(([dr, dc]) => {
                const nr = r + dr;
                const nc = c + dc;
                if (isValidPosition(nr, nc) && boardState[nr][nc] === player && !toRemove.some(([tr, tc]) => tr === nr && tc === nc)) {
                    stack.push([nr, nc]);
                }
            });
        }

        toRemove.forEach(([r, c]) => {
            boardState[r][c] = null;
            const gridPoint = document.querySelector(`#board div:nth-child(${r * 19 + c + 1})`);
            gridPoint.innerHTML = '';
        });
    }

    function updateScores() {
        let blackScore = 0, whiteScore = 0;
        boardState.forEach((row, rowIndex) => {
            row.forEach((cell, colIndex) => {
                if (cell === 'Black') {
                    blackScore++;
                } else if (cell === 'White') {
                    whiteScore++;
                }
            });
        });
        document.getElementById('black-score').textContent = blackScore;
        document.getElementById('white-score').textContent = whiteScore;
    }

    function togglePlayer() {
        currentPlayer = currentPlayer === 'Black' ? 'White' : 'Black';
        document.getElementById('current-player').textContent = currentPlayer;
    }

    initializeBoard();
});