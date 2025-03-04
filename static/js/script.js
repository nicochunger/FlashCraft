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

function updateProgressBar(percentage, message) {
    const progressContainer = document.getElementById('progress-container');
    const progressText = progressContainer.querySelector('.progress-text');
    const progressFill = progressContainer.querySelector('.progress-fill');

    progressContainer.style.display = 'block';
    progressText.textContent = message;
    progressFill.style.width = `${percentage}%`;
}

function checkProgress() {
    fetch('/progress')
        .then(response => response.json())
        .then(data => {
            if (data.complete) {
                document.getElementById('progress-container').style.display = 'none';
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

    // Show progress container and reset progress
    document.getElementById('progress-container').style.display = 'block';
    updateProgressBar(0, 'Starting process...');

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
            } else {
                alert('Error: ' + data.message);
            }
            document.getElementById('progress-container').style.display = 'none';
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while processing your request.');
            document.getElementById('progress-container').style.display = 'none';
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
