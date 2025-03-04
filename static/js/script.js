function openTab(tabName) {
    const tabs = document.getElementsByClassName('tab-content');
    const buttons = document.getElementsByClassName('tab-button');

    for (let tab of tabs) {
        tab.classList.remove('active');
    }
    for (let button of buttons) {
        button.classList.remove('active');
    }

    document.getElementById(tabName).classList.add('active');
    event.currentTarget.classList.add('active');
}

function showMessage(message, type = 'success') {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    setTimeout(() => {
        messageDiv.className = 'message';
    }, 5000);
}

// Make progress bar percentage display cleaner
function updateProgressBar(percentage, message) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = progressContainer.querySelector('.progress-bar');
    const progressText = progressContainer.querySelector('.progress-text');

    progressContainer.style.display = 'block';
    const roundedPercentage = Math.round(percentage);
    progressBar.style.width = `${roundedPercentage}%`;
    progressBar.textContent = `${roundedPercentage}%`;
    progressText.textContent = message || 'Processing...';

    // Hide result message if showing
    const resultMessage = progressContainer.querySelector('.result-message');
    resultMessage.style.display = 'none';
    resultMessage.style.opacity = '0';
}

// Ensure result message is properly displayed
function showResultMessage(message, type = 'success') {
    const progressContainer = document.getElementById('progress-container');
    const progress = progressContainer.querySelector('.progress');
    const resultMessage = progressContainer.querySelector('.result-message');
    const messageText = resultMessage.querySelector('.message-text');

    // Ensure container is visible
    progressContainer.style.display = 'block';
    progressContainer.style.opacity = '1';

    // Fade out progress elements
    progress.style.opacity = '0';
    setTimeout(() => {
        progress.style.display = 'none';

        // Show and fade in result message
        messageText.textContent = message;
        resultMessage.className = `result-message ${type}`;
        resultMessage.style.display = 'block';

        // Use a small delay to ensure the display change has taken effect
        requestAnimationFrame(() => {
            resultMessage.style.opacity = '1';
        });

        // Auto-dismiss success messages
        if (type === 'success') {
            setTimeout(() => {
                hideProgressContainer();
            }, 2000);
        }
    }, 200);
}

function hideProgressContainer() {
    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.opacity = '0';
    setTimeout(() => {
        progressContainer.style.display = 'none';
        resetProgressContainer();
    }, 200);
}

function resetProgressContainer() {
    const progressContainer = document.getElementById('progress-container');
    const progress = progressContainer.querySelector('.progress');
    const progressBar = progressContainer.querySelector('.progress-bar');
    const resultMessage = progressContainer.querySelector('.result-message');

    progress.style.display = 'block';
    progress.style.opacity = '1';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    resultMessage.style.display = 'none';
    resultMessage.style.opacity = '0';
    progressContainer.style.opacity = '1';
}

function checkProgress() {
    fetch('/progress')
        .then(response => response.json())
        .then(data => {
            if (data.complete) {
                return;
            }
            updateProgressBar(data.percentage, data.message);
            setTimeout(checkProgress, 500);
        })
        .catch(error => {
            console.error('Error checking progress:', error);
        });
}

function handleFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    const progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';
    resetProgressContainer();
    updateProgressBar(0, 'Starting process...');

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            // Stop progress checking
            clearTimeout(checkProgress);

            if (data.success) {
                showResultMessage(data.message, 'success');
            } else {
                showResultMessage(data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showResultMessage('An error occurred while processing your request.', 'error');
        });

    // Start checking progress
    checkProgress();
}

// Add event listeners when the document loads
document.addEventListener('DOMContentLoaded', () => {
    const forms = ['youtube-form', 'text-form', 'document-form'];
    forms.forEach(formId => {
        const form = document.getElementById(formId);
        if (form) {
            form.addEventListener('submit', handleFormSubmit);
        }
    });
});
