function deleteTask(taskId) {
    fetch("/delete-task", {
        method: "POST",
        body: JSON.stringify({ taskId: taskId }),
        headers: {
            "Content-Type": "application/json"
        }
    }).then((_res) => {
        window.location.href = "/";
    }).catch((error) => {
        console.error('Error deleting task:', error);
    });
  }
  