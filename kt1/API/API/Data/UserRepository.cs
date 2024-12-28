using API.Models;
using System.Collections.Concurrent;
using API.Models;

namespace API.Data
{
    public class UserRepository
    {
        private static ConcurrentDictionary<int, User> _users = new ConcurrentDictionary<int, User>();

        public IEnumerable<User> GetAll() => _users.Values;

        public User? GetById(int id) => _users.GetValueOrDefault(id);

        public User Create(User user)
        {
            user.Id = _users.Count + 1;
            _users[user.Id] = user;
            return user;
        }

        public User? Update(int id, User updatedUser)
        {
            if (_users.TryGetValue(id, out var existingUser))
            {
                existingUser.Name = updatedUser.Name;
                existingUser.Email = updatedUser.Email;
                return existingUser;
            }
            return null;
        }

        public User? Patch(int id, string name)
        {
            if (_users.TryGetValue(id, out var user))
            {
                user.Name = name;
                return user;
            }
            return null;
        }

        public bool Delete(int id) => _users.TryRemove(id, out _);
    }
}
