public class OrderService
{
    public string ProcessOrder(string orderJson)
    {
        var order = JsonConvert.DeserializeObject<Order>(orderJson);
        // validate
        if (order.Items.Count == 0) return "error";
        if (order.Total < 0) return "error";
        // apply discount
        double discount = 0;
        if (order.Total > 1000) discount = 0.1;
        if (order.Total > 5000) discount = 0.15;
        if (order.Customer.Tier == "gold") discount = discount + 0.05;
        order.Total = order.Total - (order.Total * discount);
        // save to db
        var conn = new SqlConnection("Server=prod-db;Database=orders;User Id=sa;Password=admin123;");
        conn.Open();
        var cmd = new SqlCommand("INSERT INTO Orders VALUES ('" + order.Id + "', " + order.Total + ")", conn);
        cmd.ExecuteNonQuery();
        conn.Close();
        // send email
        var smtp = new SmtpClient("smtp.example.com");
        smtp.Send("orders@example.com", order.Customer.Email, "Order confirmed", "Total: " + order.Total);
        return "ok";
    }
}
