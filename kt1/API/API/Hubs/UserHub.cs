using Microsoft.AspNetCore.SignalR;
using API.Models;
using API.Data;

namespace API.Hubs
{
    public class UserHub : Hub
    {
        private readonly UserRepository _repository;

        public UserHub()
        {
            _repository = new UserRepository();
        }

        public async Task SendUserStatus(int userId, bool isOnline)
        {
            var user = _repository.GetById(userId);
            if (user != null)
            {
                user.IsOnline = isOnline;
                await Clients.All.SendAsync("ReceiveUserStatus", userId, isOnline);
            }
        }
    }
}
