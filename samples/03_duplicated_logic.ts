function getActiveUserNames(users: any[]) {
  const result = [];
  for (let i = 0; i < users.length; i++) {
    if (users[i].active == true && users[i].deleted != true) {
      result.push(users[i].firstName + " " + users[i].lastName);
    }
  }
  return result;
}

function getActiveUserEmails(users: any[]) {
  const result = [];
  for (let i = 0; i < users.length; i++) {
    if (users[i].active == true && users[i].deleted != true) {
      result.push(users[i].email);
    }
  }
  return result;
}

function getActiveUserIds(users: any[]) {
  const result = [];
  for (let i = 0; i < users.length; i++) {
    if (users[i].active == true && users[i].deleted != true) {
      result.push(users[i].id);
    }
  }
  return result;
}
